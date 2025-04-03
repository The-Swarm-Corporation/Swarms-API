import asyncio
import json
import os
import platform
import socket
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from threading import Thread
from time import sleep, time
from typing import (
    Any,
    AsyncGenerator,
    Awaitable,
    Callable,
    Dict,
    List,
    Optional,
    Union,
)
from uuid import uuid4

import psutil
import pytz
import supabase
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Request,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from litellm import model_list
from loguru import logger
from pydantic import BaseModel, Field
from swarms import Agent, SwarmRouter, SwarmType
from swarms.structs import AgentsBuilder
from swarms.utils.any_to_str import any_to_str
from swarms.utils.litellm_tokenizer import count_tokens

# Additional imports for RAG functionality
import requests
from litellm import embedding

load_dotenv()

# --- Async generator to stream a dictionary as NDJSON ---
async def async_stream_dict(data: Dict[str, Any], delay: float = 0.0) -> AsyncGenerator[str, None]:
    for key, value in data.items():
        if delay:
            await asyncio.sleep(delay)  # Optional delay per key
        yield json.dumps({key: value}) + "\n"


# --- Function to streamify any async function that returns a dict ---
def async_streamify_dict(
    fn: Callable[..., Awaitable[Dict[str, Any]]],
    *args,
    delay: float = 0.0,
    **kwargs
) -> StreamingResponse:
    """
    Call an async function that returns a dict and stream it as NDJSON.

    Args:
        fn: An async function returning a dictionary.
        delay: Optional delay between streamed items.
        *args/**kwargs: Arguments passed to the function.

    Returns:
        StreamingResponse with NDJSON.
    """

    async def generator():
        data = await fn(*args, **kwargs)
        async for chunk in async_stream_dict(data, delay):
            yield chunk

    return StreamingResponse(generator(), media_type="application/x-ndjson")


# Load configuration
RATE_LIMIT = 100  # Max requests
TIME_WINDOW = 60  # Time window in seconds

# In-memory store for tracking requests
request_counts = defaultdict(lambda: {"count": 0, "start_time": time()})

# In-memory store for scheduled jobs
scheduled_jobs: Dict[str, Dict] = {}

app = FastAPI()


def rate_limiter(request: Request):
    client_ip = request.client.host
    current_time = time()
    client_data = request_counts[client_ip]

    # Reset count if time window has passed
    if current_time - client_data["start_time"] > TIME_WINDOW:
        client_data["count"] = 0
        client_data["start_time"] = current_time

    # Increment request count
    client_data["count"] += 1

    # Check if rate limit is exceeded
    if client_data["count"] > RATE_LIMIT:
        raise HTTPException(
            status_code=429, detail="Rate limit exceeded. Please try again later."
        )


class MCPConfig(BaseModel):
    """
    Configuration for a single MCP (Model Configuration Parameter).

    Attributes:
        url (Optional[str]): The endpoint URL for the MCP.
        parameters (Dict[str, Any]): A dictionary of parameters to be passed to the MCP.
        types (str): The type of the MCP, indicating its functionality or category.
        docs (str): Documentation or description of the MCP's purpose and usage.
    """

    url: Optional[str] = Field(None, description="The endpoint URL for the MCP.")
    parameters: Dict[str, Any] = Field(
        ..., description="A dictionary of parameters to be passed to the MCP."
    )
    types: str = Field(
        ...,
        description="The type of the MCP, indicating its functionality or category.",
    )
    docs: str = Field(
        ..., description="Documentation or description of the MCP's purpose and usage."
    )


class MultipleMCPConfig(BaseModel):
    """
    Configuration for multiple MCPs (Model Configuration Parameters).

    Attributes:
        mcps_list (List[MCPConfig]): A list of MCP configurations.
    """

    mcps_list: List[MCPConfig] = Field(..., description="A list of MCP configurations.")


class AgentSpec(BaseModel):
    agent_name: Optional[str] = Field(
        description="The unique name assigned to the agent, which identifies its role and functionality within the swarm.",
    )
    description: Optional[str] = Field(
        description="A detailed explanation of the agent's purpose, capabilities, and any specific tasks it is designed to perform.",
    )
    system_prompt: Optional[str] = Field(
        description="The initial instruction or context provided to the agent, guiding its behavior and responses during execution.",
    )
    model_name: Optional[str] = Field(
        default="gpt-4o-mini",
        description="The name of the AI model that the agent will utilize for processing tasks and generating outputs. For example: gpt-4o, gpt-4o-mini, openai/o3-mini",
    )
    auto_generate_prompt: Optional[bool] = Field(
        default=False,
        description="A flag indicating whether the agent should automatically create prompts based on the task requirements.",
    )
    max_tokens: Optional[int] = Field(
        default=8192,
        description="The maximum number of tokens that the agent is allowed to generate in its responses, limiting output length.",
    )
    temperature: Optional[float] = Field(
        default=0.5,
        description="A parameter that controls the randomness of the agent's output; lower values result in more deterministic responses.",
    )
    role: Optional[str] = Field(
        default="worker",
        description="The designated role of the agent within the swarm, which influences its behavior and interaction with other agents.",
    )
    max_loops: Optional[int] = Field(
        default=1,
        description="The maximum number of times the agent is allowed to repeat its task, enabling iterative processing if necessary.",
    )
    # New fields for RAG functionality
    rag_collection: Optional[str] = Field(
        None,
        description="The Qdrant collection name for RAG functionality. If provided, this agent will perform RAG queries.",
    )
    rag_documents: Optional[List[str]] = Field(
        None,
        description="Documents to ingest into the Qdrant collection for RAG. (List of text strings)",
    )
    # tools_dictionary: Optional[List[Dict[str, Any]]] = Field(
    #     description="A dictionary of tools that the agent can use to complete its task."
    # )


class Agents(BaseModel):
    """Configuration for a collection of agents that work together as a swarm to accomplish tasks."""

    agents: List[AgentSpec] = Field(
        description="A list containing the specifications of each agent that will participate in the swarm, detailing their roles and functionalities."
    )


class ScheduleSpec(BaseModel):
    scheduled_time: datetime = Field(
        ...,
        description="The exact date and time (in UTC) when the swarm is scheduled to execute its tasks.",
    )
    timezone: Optional[str] = Field(
        "UTC",
        description="The timezone in which the scheduled time is defined, allowing for proper scheduling across different regions.",
    )


class SwarmSpec(BaseModel):
    name: Optional[str] = Field(
        None,
        description="The name of the swarm, which serves as an identifier for the group of agents and their collective task.",
        max_length=100,
    )
    description: Optional[str] = Field(
        None,
        description="A comprehensive description of the swarm's objectives, capabilities, and intended outcomes.",
    )
    agents: Optional[List[AgentSpec]] = Field(
        None,
        description="A list of agents or specifications that define the agents participating in the swarm.",
    )
    max_loops: Optional[int] = Field(
        default=1,
        description="The maximum number of execution loops allowed for the swarm, enabling repeated processing if needed.",
    )
    swarm_type: Optional[SwarmType] = Field(
        None,
        description="The classification of the swarm, indicating its operational style and methodology.",
    )
    rearrange_flow: Optional[str] = Field(
        None,
        description="Instructions on how to rearrange the flow of tasks among agents, if applicable.",
    )
    task: Optional[str] = Field(
        None,
        description="The specific task or objective that the swarm is designed to accomplish.",
    )
    img: Optional[str] = Field(
        None,
        description="An optional image URL that may be associated with the swarm's task or representation.",
    )
    return_history: Optional[bool] = Field(
        True,
        description="A flag indicating whether the swarm should return its execution history along with the final output.",
    )
    rules: Optional[str] = Field(
        None,
        description="Guidelines or constraints that govern the behavior and interactions of the agents within the swarm.",
    )
    schedule: Optional[ScheduleSpec] = Field(
        None,
        description="Details regarding the scheduling of the swarm's execution, including timing and timezone information.",
    )
    tasks: Optional[List[str]] = Field(
        None,
        description="A list of tasks that the swarm should complete.",
    )
    messages: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="A list of messages that the swarm should complete.",
    )
    # rag_on: Optional[bool] = Field(
    #     None,
    #     description="A flag indicating whether the swarm should use RAG.",
    # )
    # collection_name: Optional[str] = Field(
    #     None,
    #     description="The name of the collection to use for RAG.",
    # )
    stream: Optional[bool] = Field(
        False,
        description="A flag indicating whether the swarm should stream its output.",
    )


class MarketplaceSwarmMetadata(BaseModel):
    """Metadata for a marketplace swarm listing"""

    name: str = Field(..., description="Unique name of the swarm")
    description: str = Field(..., description="Description of what the swarm does")
    creator_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="ID of the user who created the swarm",
    )
    tags: List[str] = Field(default=[], description="Tags to categorize the swarm")
    price: Decimal = Field(..., description="Price in credits to run the swarm")
    version: str = Field(default="1.0.0", description="Version of the swarm")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_public: bool = Field(
        default=True, description="Whether the swarm is publicly available"
    )


class MarketplaceSwarmComplete(MarketplaceSwarmMetadata):
    """Complete marketplace swarm including the actual swarm spec"""

    swarm_spec: SwarmSpec = Field(..., description="The actual swarm specification")


class AutoGenerateAgentsSpec(BaseModel):
    task: str = Field(
        None,
        description="The task that the swarm should complete.",
    )


class ScheduledJob(Thread):
    def __init__(
        self, job_id: str, scheduled_time: datetime, swarm: SwarmSpec, api_key: str
    ):
        super().__init__()
        self.job_id = job_id
        self.scheduled_time = scheduled_time
        self.swarm = swarm
        self.api_key = api_key
        self.daemon = True  # Allow the thread to be terminated when main program exits
        self.cancelled = False

    def run(self):
        while not self.cancelled:
            now = datetime.now(pytz.UTC)
            if now >= self.scheduled_time:
                try:
                    # Execute the swarm
                    asyncio.run(run_swarm_completion(self.swarm, self.api_key))
                except Exception as e:
                    logger.error(
                        f"Error executing scheduled swarm {self.job_id}: {str(e)}"
                    )
                finally:
                    # Remove the job from scheduled_jobs after execution
                    scheduled_jobs.pop(self.job_id, None)
                break
            sleep(1)  # Check every second


async def capture_telemetry(request: Request) -> Dict[str, Any]:
    """
    Captures comprehensive telemetry data from incoming requests including:
    - Request metadata (method, path, headers)
    - Client information (IP, user agent string)
    - Server information (hostname, platform)
    - System metrics (CPU, memory)
    - Timing data

    Args:
        request (Request): The FastAPI request object

    Returns:
        Dict[str, Any]: Dictionary containing telemetry data
    """
    try:
        # Get request headers
        headers = dict(request.headers)
        user_agent_string = headers.get("user-agent", "")

        # Get client IP, handling potential proxies
        client_ip = request.client.host
        forwarded_for = headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0]

        # Basic system metrics
        cpu_percent = psutil.cpu_percent()
        memory = psutil.virtual_memory()

        telemetry = {
            "request_id": str(uuid4()),
            "timestamp": datetime.utcnow().isoformat(),
            # Request data
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "client_ip": client_ip,
            # Headers and user agent info
            "headers": headers,
            "user_agent": user_agent_string,
            # Server information
            "server": {
                "hostname": socket.gethostname(),
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "processor": platform.processor() or "unknown",
            },
            # System metrics
            "system_metrics": {
                "cpu_percent": cpu_percent,
                "memory_total": memory.total,
                "memory_available": memory.available,
                "memory_percent": memory.percent,
            },
        }

        return telemetry

    except Exception as e:
        logger.error(f"Error capturing telemetry: {str(e)}")
        return {
            "error": "Failed to capture complete telemetry",
            "timestamp": datetime.utcnow().isoformat(),
        }


@lru_cache(maxsize=1)
def get_supabase_client():
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    return supabase.create_client(supabase_url, supabase_key)


@lru_cache(maxsize=1000)
def check_api_key(api_key: str) -> bool:
    supabase_client = get_supabase_client()
    response = (
        supabase_client.table("swarms_cloud_api_keys")
        .select("*")
        .eq("key", api_key)
        .execute()
    )
    return bool(response.data)


@lru_cache(maxsize=1000)
def get_user_id_from_api_key(api_key: str) -> str:
    """
    Maps an API key to its associated user ID.

    Args:
        api_key (str): The API key to look up

    Returns:
        str: The user ID associated with the API key

    Raises:
        ValueError: If the API key is invalid or not found
    """
    supabase_client = get_supabase_client()
    response = (
        supabase_client.table("swarms_cloud_api_keys")
        .select("user_id")
        .eq("key", api_key)
        .execute()
    )
    if not response.data:
        raise ValueError("Invalid API key")
    return response.data[0]["user_id"]


@lru_cache(maxsize=1000)
def verify_api_key(x_api_key: str = Header(...)) -> None:
    """
    Dependency to verify the API key.
    """
    if not check_api_key(x_api_key):
        raise HTTPException(status_code=403, detail="Invalid API Key")


async def get_api_key_logs(api_key: str) -> List[Dict[str, Any]]:
    """
    Retrieve all API request logs for a specific API key.

    Args:
        api_key: The API key to query logs for

    Returns:
        List[Dict[str, Any]]: List of log entries for the API key
    """
    try:
        supabase_client = get_supabase_client()

        # Query swarms_api_logs table for entries matching the API key
        response = (
            supabase_client.table("swarms_api_logs")
            .select("*")
            .eq("api_key", api_key)
            .execute()
        )
        return response.data

    except Exception as e:
        logger.error(f"Error retrieving API logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve API logs: {str(e)}",
        )


def validate_swarm_spec(swarm_spec: SwarmSpec) -> tuple[str, Optional[List[str]]]:
    """
    Validates the swarm specification and returns the task(s) to be executed.

    Args:
        swarm_spec: The swarm specification to validate

    Returns:
        tuple containing:
            - task string to execute (or stringified messages)
            - list of tasks if batch processing, None otherwise

    Raises:
        HTTPException: If validation fails
    """

    task = None
    tasks = None

    if (
        swarm_spec.task is None
        and swarm_spec.tasks is None
        and swarm_spec.messages is None
    ):
        raise HTTPException(
            status_code=400,
            detail="There is no task or tasks or messages provided. Please provide a valid task description to proceed.",
        )

    if swarm_spec.task is not None:
        task = swarm_spec.task
    elif swarm_spec.messages is not None:
        task = any_to_str(swarm_spec.messages)
    elif swarm_spec.task and swarm_spec.messages is not None:
        task = f"{any_to_str(swarm_spec.messages)} \n\n User: {swarm_spec.task}"
    elif swarm_spec.tasks is not None:
        tasks = swarm_spec.tasks

    return task, tasks


def create_single_agent(agent_spec: Union[AgentSpec, dict]) -> Agent:
    """
    Creates a single agent.

    Args:
        agent_spec: Agent specification (either AgentSpec object or dict)

    Returns:
        Created Agent instance

    Raises:
        HTTPException: If agent creation fails
    """
    try:
        # Convert dict to AgentSpec if needed
        if isinstance(agent_spec, dict):
            agent_spec = AgentSpec(**agent_spec)

        # Validate required fields
        if not agent_spec.agent_name:
            raise ValueError("Agent name is required.")
        if not agent_spec.model_name:
            raise ValueError("Model name is required.")

        # if agent_spec.tools_dictionary is not None:
        #     tools_list_dictionary = agent_spec.tools_dictionary
        # else:
        #     tools_list_dictionary = None

        # Create the agent
        agent = Agent(
            agent_name=agent_spec.agent_name,
            description=agent_spec.description,
            system_prompt=agent_spec.system_prompt,
            model_name=agent_spec.model_name or "gpt-4o-mini",
            auto_generate_prompt=agent_spec.auto_generate_prompt or False,
            max_tokens=agent_spec.max_tokens or 8192,
            temperature=agent_spec.temperature or 0.5,
            role=agent_spec.role or "worker",
            max_loops=agent_spec.max_loops or 1,
            dynamic_temperature_enabled=True,
            # tools_list_dictionary=tools_list_dictionary,
        )

        logger.info("Successfully created agent: {}", agent_spec.agent_name)
        return agent

    except ValueError as ve:
        logger.error(
            "Validation error for agent {}: {}",
            getattr(agent_spec, "agent_name", "unknown"),
            str(ve),
        )
        raise HTTPException(
            status_code=400, detail=f"Agent validation error: {str(ve)}"
        )
    except Exception as e:
        logger.error(
            "Error creating agent {}: {}",
            getattr(agent_spec, "agent_name", "unknown"),
            str(e),
        )
        raise HTTPException(status_code=500, detail=f"Failed to create agent: {str(e)}")


def create_swarm(swarm_spec: SwarmSpec, api_key: str):
    """
    Creates and executes a swarm based on the provided specification.

    Args:
        swarm_spec: The swarm specification
        api_key: API key for authentication and billing

    Returns:
        The swarm execution results

    Raises:
        HTTPException: If swarm creation or execution fails
    """
    try:
        # Validate the swarm spec

        task, tasks = validate_swarm_spec(swarm_spec)

        # Create agents in parallel if specified
        agents = []
        if swarm_spec.agents is not None:
            # Use ThreadPoolExecutor for parallel agent creation
            with ThreadPoolExecutor(
                max_workers=min(len(swarm_spec.agents), 10)
            ) as executor:
                # Submit all agent creation tasks
                future_to_agent = {
                    executor.submit(create_single_agent, agent_spec): agent_spec
                    for agent_spec in swarm_spec.agents
                }

                # Collect results as they complete
                for future in as_completed(future_to_agent):
                    agent_spec = future_to_agent[future]
                    try:
                        agent = future.result()
                        agents.append(agent)
                    except HTTPException:
                        # Re-raise HTTP exceptions with original status code
                        raise
                    except Exception as e:
                        logger.error(
                            "Error creating agent {}: {}",
                            getattr(agent_spec, "agent_name", "unknown"),
                            str(e),
                        )
                        raise HTTPException(
                            status_code=500, detail=f"Failed to create agent: {str(e)}"
                        )

        # Create and configure the swarm
        swarm = SwarmRouter(
            name=swarm_spec.name,
            description=swarm_spec.description,
            agents=agents,
            max_loops=swarm_spec.max_loops,
            swarm_type=swarm_spec.swarm_type,
            output_type="dict",
            return_entire_history=False,
            rules=swarm_spec.rules,
            rearrange_flow=swarm_spec.rearrange_flow,
        )

        # Calculate costs and execute
        start_time = time()

        if task is not None:
            output = swarm.run(task=task)
        elif tasks is not None:
            output = swarm.batch_run(tasks=tasks)
        else:
            output = swarm.run(task=task)

        # Calculate execution time and costs
        execution_time = time() - start_time
        cost_info = calculate_swarm_cost(
            agents=agents,
            input_text=swarm_spec.task,
            execution_time=execution_time,
            agent_outputs=output,
        )

        # Deduct credits
        deduct_credits(
            api_key,
            cost_info["total_cost"],
            f"swarm_execution_{swarm_spec.name}",
        )

        logger.info("Swarm task executed successfully: {}", swarm_spec.task)
        return output

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating swarm: {}", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create swarm: {str(e)}",
        )


# --- RAG Pipeline Implementation ---
# This code implements unified indexing and retrieval operations with Qdrant using LiteLLM embeddings.
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

def rag_pipeline(operation: str, collection_name: str, data: Optional[List[str]] = None, query: Optional[str] = None, vector_dim: int = 1536, embedding_model: str = "text-embedding-3-small"
) -> Union[bool, tuple, None]:
    """Unified RAG pipeline for indexing and retrieval operations."""
    # Fixed constants
    C = {"metric": "Cosine", "chunk_size": 500, "overlap": 50, "batch": 50, "limit": 3, "threshold": 0.35}
    
    # Helper function for API requests
    def _req(method, path, json=None, params=None):
        if not QDRANT_URL or not QDRANT_API_KEY:
            return None
        try:
            resp = requests.request(
                method, 
                f"{QDRANT_URL}{path}", 
                headers={"api-key": QDRANT_API_KEY, "Content-Type": "application/json"},
                json=json,
                params=params,
                timeout=60
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            print(f"Qdrant API Error: {str(e)}")
            return None
    
    # LiteLLM embedding function
    def _embed(texts):
        try:
            response = embedding(model=embedding_model, input=texts)
            return [item['embedding'] for item in response.data]
        except Exception as e:
            print(f"Embedding Error: {str(e)}")
            return None
    
    # INDEXING OPERATION
    if operation == "index" and data:
        # Ensure collection exists
        exists = _req("GET", f"/collections/{collection_name}/exists")
        if not exists or exists.get("status") != "ok":
            return False
            
        if not exists.get("result", {}).get("exists", False):
            if not _req("PUT", f"/collections/{collection_name}", 
                      json={"vectors": {"size": vector_dim, "distance": C["metric"]}}):
                return False
        
        # Process documents into chunks
        chunks = []
        for doc_idx, content in enumerate([d for d in data if isinstance(d, str) and d.strip()]):
            start, chunk_idx = 0, 0
            while start < len(content):
                end = min(start + C["chunk_size"], len(content))
                chunk_text = content[start:end].strip()
                if chunk_text:
                    chunks.append({
                        "id": str(uuid4()),
                        "text": chunk_text,
                        "meta": {"doc_idx": doc_idx, "chunk_idx": chunk_idx}
                    })
                    chunk_idx += 1
                start = end - C["overlap"] if end - C["overlap"] > start else start + 1
        
        if not chunks:
            return True
            
        # Embed and upsert in batches
        success = True
        for i in range(0, len(chunks), C["batch"]):
            batch = chunks[i:i + C["batch"]]
            batch_texts = [item['text'] for item in batch]
            embeddings = _embed(batch_texts)
            
            if not embeddings or len(embeddings) != len(batch):
                success = False
                continue
                
            points = [{
                "id": item["id"],
                "vector": emb,
                "payload": {"content": item["text"], "metadata": item["meta"]}
            } for item, emb in zip(batch, embeddings)]
            
            resp = _req("PUT", f"/collections/{collection_name}/points", 
                      json={"points": points}, params={"wait": "true"})
            if not resp or resp.get("result", {}).get("status") != "completed":
                success = False
                
        return success
        
    # RETRIEVAL OPERATION
    elif operation == "retrieve" and query:
        query_emb = _embed([query])[0]
        resp = _req("POST", f"/collections/{collection_name}/points/query", json={
            "query": query_emb,
            "limit": C["limit"],
            "with_payload": True,
            "with_vector": False,
            "score_threshold": C["threshold"]
        })
        
        if not resp or resp.get("status") != "ok":
            return None, None
            
        results = resp.get("result", {}).get("points", [])
        if not results:
            return "No relevant context found.", []
            
        context = []
        sources = []
        for i, doc in enumerate(results):
            text = doc.get("payload", {}).get("content", "[Missing]")
            meta = doc.get("payload", {}).get("metadata", {})
            score = doc.get("score", 0.0)
            
            context.append(f"Context {i+1} (Score: {score:.4f}):\n{text}")
            meta['score'] = score
            sources.append(meta)
            
        return "\n\n---\n\n".join(context), sources
        
    return None


async def log_api_request(api_key: str, data: Dict[str, Any]) -> None:
    """
    Log API request data to Supabase swarms_api_logs table.

    Args:
        api_key: The API key used for the request
        data: Dictionary containing request data to log
    """
    try:
        supabase_client = get_supabase_client()

        # Create log entry
        log_entry = {
            "api_key": api_key,
            "data": data,
        }

        # Insert into swarms_api_logs table
        response = supabase_client.table("swarms_api_logs").insert(log_entry).execute()

        if not response.data:
            logger.error("Failed to log API request")

    except Exception as e:
        logger.error(f"Error logging API request: {str(e)}")


async def run_swarm_completion(
    swarm: SwarmSpec, x_api_key: str = None
) -> Dict[str, Any]:
    """
    Run a swarm with the specified task.
    """
    try:
        swarm_name = swarm.name

        # --- RAG Integration ---
        # For each agent with rag_collection set, index the documents (if any)
        # and then retrieve context based on the swarm task.
        if swarm.agents:
            for agent_spec in swarm.agents:
                if agent_spec.rag_collection:
                    if agent_spec.rag_documents and len(agent_spec.rag_documents) > 0:
                        indexing_success = rag_pipeline("index", agent_spec.rag_collection, data=agent_spec.rag_documents)
                        if not indexing_success:
                            logger.error(f"Failed to index documents for collection {agent_spec.rag_collection}")
                    rag_context, rag_sources = rag_pipeline("retrieve", agent_spec.rag_collection, query=swarm.task)
                    if rag_context:
                        agent_spec.system_prompt = (agent_spec.system_prompt or "") + "\n\nRAG Context:\n" + rag_context

        agents = swarm.agents

        await log_api_request(x_api_key, swarm.model_dump())

        # Log start of swarm execution
        logger.info(f"Starting swarm {swarm_name} with {len(agents)} agents")

        # Create and run the swarm
        logger.debug(f"Creating swarm object for {swarm_name}")

        time()

        try:
            result = create_swarm(swarm, x_api_key)
        except Exception as e:
            logger.error(f"Error running swarm: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to run swarm: {e}",
            )

        logger.debug(f"Running swarm task: {swarm.task}")

        if swarm.swarm_type == "MALT":
            length_of_agents = 14
        else:
            length_of_agents = len(agents)

        # Format the response
        response = {
            "status": "success",
            "swarm_name": swarm_name,
            "description": swarm.description,
            "swarm_type": swarm.swarm_type,
            "task": swarm.task,
            "output": result,
            "number_of_agents": length_of_agents,
            # "input_config": swarm.model_dump(),
        }

        if swarm.tasks is not None:
            response["tasks"] = swarm.tasks

        if swarm.messages is not None:
            response["messages"] = swarm.messages

        logger.info(response)
        await log_api_request(x_api_key, response)

        return response

    except HTTPException as http_exc:
        logger.error("HTTPException occurred: {}", http_exc.detail)
        raise
    except Exception as e:
        logger.error("Error running swarm {}: {}", swarm_name, str(e))
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run swarm: {e}",
        )


def deduct_credits(api_key: str, amount: float, product_name: str) -> None:
    """
    Deducts the specified amount of credits for the user identified by api_key,
    preferring to use free_credit before using regular credit, and logs the transaction.
    """
    supabase_client = get_supabase_client()
    user_id = get_user_id_from_api_key(api_key)

    # 1. Retrieve the user's credit record
    response = (
        supabase_client.table("swarms_cloud_users_credits")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User credits record not found.",
        )

    record = response.data[0]
    # Use Decimal for precise arithmetic
    available_credit = Decimal(record["credit"])
    free_credit = Decimal(record.get("free_credit", "0"))
    deduction = Decimal(str(amount))

    print(
        f"Available credit: {available_credit}, Free credit: {free_credit}, Deduction: {deduction}"
    )

    # 2. Verify sufficient total credits are available
    if (available_credit + free_credit) < deduction:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Insufficient credits. Fill your credit card in the dashboard at https://swarms.world/platform/account",
        )

    # 3. Log the transaction
    log_response = (
        supabase_client.table("swarms_cloud_services")
        .insert(
            {
                "user_id": user_id,
                "api_key": api_key,
                "charge_credit": int(
                    deduction
                ),  # Assuming credits are stored as integers
                "product_name": product_name,
            }
        )
        .execute()
    )
    if not log_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to log the credit transaction.",
        )

    # 4. Deduct credits: use free_credit first, then deduct the remainder from available_credit
    if free_credit >= deduction:
        free_credit -= deduction
    else:
        remainder = deduction - free_credit
        free_credit = Decimal("0")
        available_credit -= remainder

    update_response = (
        supabase_client.table("swarms_cloud_users_credits")
        .update(
            {
                "credit": str(available_credit),
                "free_credit": str(free_credit),
            }
        )
        .eq("user_id", user_id)
        .execute()
    )
    if not update_response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update credits.",
        )


def calculate_swarm_cost(
    agents: List[Any],
    input_text: str,
    execution_time: float,
    agent_outputs: Union[List[Dict[str, str]], str] = None,  # Update agent_outputs type
) -> Dict[str, Any]:
    """
    Calculate the cost of running a swarm based on agents, tokens, and execution time.
    Includes system prompts, agent memory, and scaled output costs.

    Args:
        agents: List of agents used in the swarm
        input_text: The input task/prompt text
        execution_time: Time taken to execute in seconds
        agent_outputs: List of output texts from each agent or a list of dictionaries

    Returns:
        Dict containing cost breakdown and total cost
    """
    # Base costs per unit (these could be moved to environment variables)
    COST_PER_AGENT = 0.01  # Base cost per agent
    COST_PER_1M_INPUT_TOKENS = 2.00  # Cost per 1M input tokens
    COST_PER_1M_OUTPUT_TOKENS = 4.50  # Cost per 1M output tokens

    # Get current time in California timezone
    california_tz = pytz.timezone("America/Los_Angeles")
    current_time = datetime.now(california_tz)
    is_night_time = current_time.hour >= 20 or current_time.hour < 6  # 8 PM to 6 AM

    try:
        # Calculate input tokens for task
        task_tokens = count_tokens(input_text)

        # Calculate total input tokens including system prompts and memory for each agent
        total_input_tokens = 0
        total_output_tokens = 0
        per_agent_tokens = {}
        agent_cost = 0

        for i, agent in enumerate(agents):
            agent_input_tokens = task_tokens  # Base task tokens

            # Add system prompt tokens if present
            if agent.system_prompt:
                agent_input_tokens += count_tokens(agent.system_prompt)

            # Add memory tokens if available
            try:
                memory = agent.short_memory.return_history_as_string()
                if memory:
                    memory_tokens = count_tokens(str(memory))
                    agent_input_tokens += memory_tokens
            except Exception as e:
                logger.warning(
                    f"Could not get memory for agent {agent.agent_name}: {str(e)}"
                )

            # Calculate actual output tokens if available, otherwise estimate
            if agent_outputs:
                if isinstance(agent_outputs, list):
                    # Sum tokens for each dictionary's content
                    agent_output_tokens = sum(
                        count_tokens(message["content"]) for message in agent_outputs
                    )
                elif isinstance(agent_outputs, str):
                    agent_output_tokens = count_tokens(agent_outputs)
                elif isinstance(agent_outputs, dict):
                    agent_output_tokens = count_tokens(any_to_str(agent_outputs))
                else:
                    agent_output_tokens = any_to_str(agent_outputs)
            else:
                agent_output_tokens = int(
                    agent_input_tokens * 2.5
                )  # Estimated output tokens

            # Store per-agent token counts
            per_agent_tokens[agent.agent_name] = {
                "input_tokens": agent_input_tokens,
                "output_tokens": agent_output_tokens,
                "total_tokens": agent_input_tokens + agent_output_tokens,
            }

            # Add to totals
            total_input_tokens += agent_input_tokens
            total_output_tokens += agent_output_tokens

        # Calculate costs (convert to millions of tokens)
        agent_cost = len(agents) * COST_PER_AGENT
        input_token_cost = (
            (total_input_tokens / 1_000_000) * COST_PER_1M_INPUT_TOKENS * len(agents)
        )
        output_token_cost = (
            (total_output_tokens / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS * len(agents)
        )

        # Apply discount during California night time hours
        if is_night_time:
            input_token_cost *= 0.25  # 75% discount
            output_token_cost *= 0.25  # 75% discount

        # Calculate total cost
        total_cost = agent_cost + input_token_cost + output_token_cost

        output = {
            "cost_breakdown": {
                "agent_cost": round(agent_cost, 6),
                "input_token_cost": round(input_token_cost, 6),
                "output_token_cost": round(output_token_cost, 6),
                "token_counts": {
                    "total_input_tokens": total_input_tokens,
                    "total_output_tokens": total_output_tokens,
                    "total_tokens": total_input_tokens + total_output_tokens,
                    "per_agent": per_agent_tokens,
                },
                "num_agents": len(agents),
                "execution_time_seconds": round(execution_time, 2),
            },
            "total_cost": round(total_cost, 6),
        }

        return output

    except Exception as e:
        logger.error(f"Error calculating swarm cost: {str(e)}")
        raise ValueError(f"Failed to calculate swarm cost: {str(e)}")


async def auto_generate_agents(request: AutoGenerateAgentsSpec):
    """
    Automatically generate agents for a given task.
    """
    agents_builder = AgentsBuilder(return_dictionary=True)

    start_time = time()
    agents = await asyncio.to_thread(agents_builder.run, task=request.task)
    end_time = time()

    calculate_swarm_cost(
        agents=agents_builder,
        input_text=request.task + agents_builder.system_prompt,
        execution_time=end_time - start_time,
        agent_outputs=any_to_str(agents),
    )

    return agents


async def get_swarm_types() -> List[str]:
    """Returns a list of available swarm types"""
    return [
        "AgentRearrange",
        "MixtureOfAgents",
        "SpreadSheetSwarm",
        "SequentialWorkflow",
        "ConcurrentWorkflow",
        "GroupChat",
        "MultiAgentRouter",
        "AutoSwarmBuilder",
        "HiearchicalSwarm",
        "auto",
        "MajorityVoting",
        "MALT",
        "DeepResearchSwarm",
    ]


# --- FastAPI Application Setup ---

app = FastAPI(
    title="Swarm Agent API",
    description="API for managing and executing Python agents in the cloud without Docker/Kubernetes.",
    version="1.0.0",
    # debug=True,
)

# Enable CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "Welcome to the Swarm API. Check out the docs at https://docs.swarms.world"
    }


@app.middleware("http")
async def telemetry_middleware(request: Request, call_next):
    """
    Middleware to capture telemetry for all requests and log to database
    """
    start_time = time()

    # Capture initial telemetry
    telemetry = await capture_telemetry(request)

    # Add request start time
    telemetry["request_timing"] = {
        "start_time": start_time,
        "start_timestamp": datetime.utcnow().isoformat(),
    }

    # Store telemetry in request state for access in route handlers
    request.state.telemetry = telemetry

    try:
        # Process the request
        response = await call_next(request)

        # Calculate request duration
        duration = time() - start_time

        # Update telemetry with response data
        telemetry.update(
            {
                "response": {
                    "status_code": response.status_code,
                    "duration_seconds": duration,
                }
            }
        )

        # Try to get API key from headers
        api_key = request.headers.get("x-api-key")

        # Log telemetry to database if we have an API key
        if api_key:
            try:
                await log_api_request(
                    api_key,
                    {
                        "telemetry": telemetry,
                        "path": str(request.url.path),
                        "method": request.method,
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                )
            except Exception as e:
                logger.error(f"Failed to log telemetry to database: {str(e)}")

        return response

    except Exception as e:
        # Update telemetry with error information
        telemetry.update(
            {
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "duration_seconds": time() - start_time,
                }
            }
        )

        # Try to log error telemetry if we have an API key
        api_key = request.headers.get("x-api-key")
        if api_key:
            try:
                await log_api_request(
                    api_key,
                    {
                        "telemetry": telemetry,
                        "path": str(request.url.path),
                        "method": request.method,
                        "timestamp": datetime.utcnow().isoformat(),
                        "error": True,
                    },
                )
            except Exception as log_error:
                logger.error(f"Failed to log error telemetry: {str(log_error)}")

        raise  # Re-raise the original exception


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get(
    "/v1/swarms/available",
    dependencies=[Depends(rate_limiter)],
)
async def check_swarm_types() -> Dict[str, Any]:
    """
    Check the available swarm types.
    """
    out = {
        "success": True,
        "swarm_types": get_swarm_types(),
    }

    return out


@app.post(
    "/v1/swarm/completions",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
async def run_swarm(swarm: SwarmSpec, x_api_key=Header(...)) -> Dict[str, Any]:
    """
    Run a swarm with the specified task.
    """
    # return await run_swarm_completion(swarm, x_api_key)

    if swarm.stream is True:
        return async_streamify_dict(run_swarm_completion)(swarm, x_api_key)
    else:
        return await run_swarm_completion(swarm, x_api_key)


@app.post(
    "/v1/swarm/batch/completions",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
def run_batch_completions(
    swarms: List[SwarmSpec], x_api_key=Header(...)
) -> List[Dict[str, Any]]:
    """
    Run a batch of swarms with the specified tasks using a thread pool.
    """
    results = []

    def process_swarm(swarm):
        try:
            # Create and run the swarm directly
            result = create_swarm(swarm, x_api_key)
            return {"status": "success", "swarm_name": swarm.name, "result": result}
        except HTTPException as http_exc:
            logger.error("HTTPException occurred: {}", http_exc.detail)
            return {
                "status": "error",
                "swarm_name": swarm.name,
                "detail": http_exc.detail,
            }
        except Exception as e:
            logger.error("Error running swarm {}: {}", swarm.name, str(e))
            logger.exception(e)
            return {
                "status": "error",
                "swarm_name": swarm.name,
                "detail": f"Failed to run swarm: {str(e)}",
            }

    # Use ThreadPoolExecutor for concurrent execution
    with ThreadPoolExecutor(max_workers=min(len(swarms), 10)) as executor:
        # Submit all swarms to the thread pool
        future_to_swarm = {
            executor.submit(process_swarm, swarm): swarm for swarm in swarms
        }

        # Collect results as they complete
        for future in as_completed(future_to_swarm):
            result = future.result()
            results.append(result)

    return results


# @app.post(
#     "/v1/swarms/marketplace/publish",
#     dependencies=[
#         Depends(verify_api_key),
#         Depends(rate_limiter),
#     ],
# )
# async def publish_marketplace_swarm(
#     swarm: MarketplaceSwarmComplete, x_api_key: str = Header(...)
# ) -> Dict[str, Any]:
#     """
#     Publish a swarm to the marketplace.
#     """
#     try:

#         # Set the creator ID
#         swarm.creator_id = str(uuid.uuid4())

#         await log_api_request(
#             x_api_key,
#             {"action": "publish_marketplace_swarm", "swarm_config": swarm.model_dump()},
#         )

#         return {
#             "status": "success",
#             "message": "Swarm published successfully",
#             "swarm": swarm.model_dump(),
#         }

#     except Exception as e:
#         logger.error(f"Error publishing marketplace swarm: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to publish swarm: {str(e)}",
#         )


# Add this new endpoint
@app.get(
    "/v1/swarm/logs",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
async def get_logs(x_api_key: str = Header(...)) -> Dict[str, Any]:
    """
    Get all API request logs for the provided API key.
    """
    try:
        logs = await get_api_key_logs(x_api_key)
        return {"status": "success", "count": len(logs), "logs": logs}
    except Exception as e:
        logger.error(f"Error in get_logs endpoint: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.get(
    "/v1/models/available",
    dependencies=[
        Depends(rate_limiter),
    ],
)
async def get_available_models() -> Dict[str, Any]:
    """
    Get all available models.
    """
    out = {
        "success": True,
        "models": model_list,
    }
    return out


@app.post(
    "/v1/swarm/schedule",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
async def schedule_swarm(
    swarm: SwarmSpec, x_api_key: str = Header(...)
) -> Dict[str, Any]:
    """
    Schedule a swarm to run at a specific time.
    """
    if not swarm.schedule:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schedule information is required",
        )

    try:
        # Generate a unique job ID
        job_id = f"swarm_{swarm.name}_{int(time())}"

        # Create and start the scheduled job
        job = ScheduledJob(
            job_id=job_id,
            scheduled_time=swarm.schedule.scheduled_time,
            swarm=swarm,
            api_key=x_api_key,
        )
        job.start()

        # Store the job information
        scheduled_jobs[job_id] = {
            "job": job,
            "swarm_name": swarm.name,
            "scheduled_time": swarm.schedule.scheduled_time,
            "timezone": swarm.schedule.timezone,
        }

        # Log the scheduling
        await log_api_request(
            x_api_key,
            {
                "action": "schedule_swarm",
                "swarm_name": swarm.name,
                "scheduled_time": swarm.schedule.scheduled_time.isoformat(),
                "job_id": job_id,
            },
        )

        return {
            "status": "success",
            "message": "Swarm scheduled successfully",
            "job_id": job_id,
            "scheduled_time": swarm.schedule.scheduled_time,
            "timezone": swarm.schedule.timezone,
        }

    except Exception as e:
        logger.error(f"Error scheduling swarm: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule swarm: {str(e)}",
        )


@app.get(
    "/v1/swarm/schedule",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
async def get_scheduled_jobs(x_api_key: str = Header(...)) -> Dict[str, Any]:
    """
    Get all scheduled swarm jobs.
    """
    try:
        jobs_list = []
        current_time = datetime.now(pytz.UTC)

        # Clean up completed jobs
        completed_jobs = [
            job_id
            for job_id, job_info in scheduled_jobs.items()
            if current_time >= job_info["scheduled_time"]
        ]
        for job_id in completed_jobs:
            scheduled_jobs.pop(job_id, None)

        # Get active jobs
        for job_id, job_info in scheduled_jobs.items():
            jobs_list.append(
                {
                    "job_id": job_id,
                    "swarm_name": job_info["swarm_name"],
                    "scheduled_time": job_info["scheduled_time"].isoformat(),
                    "timezone": job_info["timezone"],
                }
            )

        return {"status": "success", "scheduled_jobs": jobs_list}

    except Exception as e:
        logger.error(f"Error retrieving scheduled jobs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve scheduled jobs: {str(e)}",
        )


@app.delete(
    "/v1/swarm/schedule/{job_id}",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
async def cancel_scheduled_job(
    job_id: str, x_api_key: str = Header(...)
) -> Dict[str, Any]:
    """
    Cancel a scheduled swarm job.
    """
    try:
        if job_id not in scheduled_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Scheduled job not found"
            )

        # Cancel and remove the job
        job_info = scheduled_jobs[job_id]
        job_info["job"].cancelled = True
        scheduled_jobs.pop(job_id)

        await log_api_request(
            x_api_key, {"action": "cancel_scheduled_job", "job_id": job_id}
        )

        return {
            "status": "success",
            "message": "Scheduled job cancelled successfully",
            "job_id": job_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling scheduled job: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel scheduled job: {str(e)}",
        )


# --- Main Entrypoint ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)

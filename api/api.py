import asyncio
import os
import platform
import secrets
import socket
import string
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from decimal import Decimal
from functools import lru_cache
from time import time
from typing import (
    Any,
    Dict,
    List,
    Literal,
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
from litellm import model_list
from loguru import logger
from pydantic import BaseModel, Field
from swarms import Agent, SwarmRouter
from swarms.utils.any_to_str import any_to_str
from swarms.utils.litellm_tokenizer import count_tokens

# Literal of output types
OutputType = Literal[
    "all",
    "final",
    "list",
    "dict",
    ".json",
    ".md",
    ".txt",
    ".yaml",
    ".toml",
    "string",
    "str",
]

SwarmType = Literal[
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

agent_types = Literal[
    "reasoning-duo",
    "self-consistency",
    "ire",
    "reasoning-agent",
    "consistency-agent",
    "ire-agent",
    "ReflexionAgent",
    "GKPAgent",
    "AgentJudge",
]


# Use the OutputType for type annotations
output_type: OutputType


load_dotenv()

# Define rate limit parameters
RATE_LIMIT = 100  # Max requests
TIME_WINDOW = 60  # Time window in seconds

# In-memory store for tracking requests
request_counts = defaultdict(lambda: {"count": 0, "start_time": time()})

# In-memory store for scheduled jobs
scheduled_jobs: Dict[str, Dict] = {}

app = FastAPI(
    title="Swarms API",
    description="The Swarms API is a powerful tool for managing and executing multi-agent systems with ease. It provides a flexible model support, diverse swarm architectures, dynamic agent configuration, and real-time monitoring capabilities.",
)


def generate_key(prefix: str = "swarms") -> str:
    """
    Generates an API key similar to OpenAI's format (sk-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX).

    Args:
        prefix (str): The prefix for the API key. Defaults to "sk".

    Returns:
        str: An API key string in format: prefix-<48 random characters>
    """
    # Create random string of letters and numbers
    alphabet = string.ascii_letters + string.digits
    random_part = "".join(secrets.choice(alphabet) for _ in range(28))
    return f"{prefix}-{random_part}"


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


class AgentSpec(BaseModel):
    agent_name: Optional[str] = Field(
        # default=None,
        description="The unique name assigned to the agent, which identifies its role and functionality within the swarm.",
    )
    description: Optional[str] = Field(
        default=None,
        description="A detailed explanation of the agent's purpose, capabilities, and any specific tasks it is designed to perform.",
    )
    system_prompt: Optional[str] = Field(
        default=None,
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
    tools_dictionary: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="A dictionary of tools that the agent can use to complete its task.",
    )
    # mcp_servers: Optional[str] = Field(
    #     description="A list of MCP servers that the agent can use to complete its task."
    # )

    class Config:
        arbitrary_types_allowed = True


class AgentCompletion(BaseModel):
    agent_config: AgentSpec = Field(
        ..., description="The configuration of the agent to be completed."
    )
    task: str = Field(..., description="The task to be completed by the agent.")

    class Config:
        arbitrary_types_allowed = True


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
    stream: Optional[bool] = Field(
        False,
        description="A flag indicating whether the swarm should stream its output.",
    )
    service_tier: Optional[str] = Field(
        "standard",
        description="The service tier to use for processing. Options: 'standard' (default) or 'flex' for lower cost but slower processing.",
    )

    class Config:
        arbitrary_types_allowed = True


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
            "timestamp": datetime.now(UTC).isoformat(),
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
            "timestamp": datetime.now(UTC).isoformat(),
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

        # if agent_spec.tools_dictionary is not None:
        #     output_type = "dict"
        # else:
        #     output_type = "final"

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
            tools_list_dictionary=agent_spec.tools_dictionary,
            output_type="str-all-except-first",
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

        output = (
            swarm.run(task=task)
            if task is not None
            else (
                swarm.batch_run(tasks=tasks)
                if tasks is not None
                else swarm.run(task=task)
            )
        )

        # Calculate execution time and costs
        execution_time = time() - start_time

        # Calculate costs
        cost_info = calculate_swarm_cost(
            agents=agents,
            input_text=swarm_spec.task,
            execution_time=execution_time,
            agent_outputs=output,
            service_tier=swarm_spec.service_tier,
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


# Add this function after your get_supabase_client() function
async def log_api_request(
    api_key: str, data: Union[Dict[str, Any], BaseModel, list]
) -> None:
    """
    Log API request data to Supabase swarms_api_logs table.

    Args:
        api_key: The API key used for the request
        data: Dictionary containing request data to log
    """
    try:

        if isinstance(data, BaseModel):
            data = data.model_dump()

        if isinstance(data, list):
            data = [
                item.model_dump() if isinstance(item, BaseModel) else item
                for item in data
            ]

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


# Add cache dictionary at module level
context_cache = {}
CACHE_TTL = 3600  # 1 hour in seconds
MAX_CACHE_SIZE = 1000  # Maximum number of cache entries
CACHE_CLEANUP_INTERVAL = 300  # Clean up cache every 5 minutes


def generate_cache_key(swarm: SwarmSpec) -> str:
    """
    Generate a unique cache key for a swarm configuration.
    Includes relevant fields that affect the output.
    """
    key_parts = [
        swarm.name,
        swarm.task,
        swarm.swarm_type,
        str(swarm.max_loops),
        str(swarm.return_history),
    ]

    # Add agent configurations to the key
    if swarm.agents:
        agent_configs = []
        for agent in swarm.agents:
            agent_config = {
                "name": agent.agent_name,
                "model": agent.model_name,
                "prompt": agent.system_prompt,
                "temp": agent.temperature,
                "max_loops": agent.max_loops,
            }
            agent_configs.append(str(agent_config))
        key_parts.extend(agent_configs)

    # Add tasks and messages if present
    if swarm.tasks:
        key_parts.append(str(swarm.tasks))
    if swarm.messages:
        key_parts.append(str(swarm.messages))

    return "|".join(key_parts)


def cleanup_cache():
    """
    Clean up expired cache entries and enforce size limits.
    """
    current_time = time()

    # Remove expired entries
    expired_keys = [
        key
        for key, value in context_cache.items()
        if current_time - value["timestamp"] >= CACHE_TTL
    ]
    for key in expired_keys:
        del context_cache[key]

    # If still over size limit, remove oldest entries
    if len(context_cache) > MAX_CACHE_SIZE:
        sorted_entries = sorted(context_cache.items(), key=lambda x: x[1]["timestamp"])
        entries_to_remove = sorted_entries[: len(context_cache) - MAX_CACHE_SIZE]
        for key, _ in entries_to_remove:
            del context_cache[key]


async def run_swarm_completion(
    swarm: SwarmSpec, x_api_key: str = None
) -> Dict[str, Any]:
    """
    Run a swarm with the specified task.
    """
    try:
        swarm_name = swarm.name
        agents = swarm.agents

        # Generate cache key based on swarm configuration
        cache_key = generate_cache_key(swarm)

        # Check if we have a valid cached result
        current_time = time()
        if cache_key in context_cache:
            cached_result = context_cache[cache_key]
            if current_time - cached_result["timestamp"] < CACHE_TTL:
                logger.info(f"Using cached result for swarm {swarm_name}")
                return cached_result["response"]

        await log_api_request(x_api_key, swarm.model_dump())

        # Log start of swarm execution
        logger.info(f"Starting swarm {swarm_name} with {len(agents)} agents")

        # Create and run the swarm
        logger.debug(f"Creating swarm object for {swarm_name}")

        # Handle flex processing
        max_retries = 3 if swarm.service_tier == "flex" else 1

        for attempt in range(max_retries):
            try:
                result = create_swarm(swarm, x_api_key)
                break
            except HTTPException as e:
                if e.status_code == 429 and swarm.service_tier == "flex":
                    # Resource unavailable error in flex mode
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        backoff_time = (2**attempt) * 5  # 5, 10, 20 seconds
                        logger.info(
                            f"Resource unavailable, retrying in {backoff_time} seconds..."
                        )
                        await asyncio.sleep(backoff_time)
                        continue
                raise
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

        # Job id
        job_id = generate_key()

        # Format the response
        response = {
            "job_id": job_id,
            "status": "success",
            "swarm_name": swarm_name,
            "description": swarm.description,
            "swarm_type": swarm.swarm_type,
            "output": result,
            "number_of_agents": length_of_agents,
            "service_tier": swarm.service_tier,
        }

        if swarm.tasks is not None:
            response["tasks"] = swarm.tasks

        if swarm.messages is not None:
            response["messages"] = swarm.messages

        # Cache the response
        context_cache[cache_key] = {"response": response, "timestamp": current_time}

        # Clean up cache periodically
        if current_time % CACHE_CLEANUP_INTERVAL < 1:  # Check every ~5 minutes
            cleanup_cache()

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
    service_tier: str = "standard",
) -> Dict[str, Any]:
    """
    Calculate the cost of running a swarm based on agents, tokens, and execution time.
    Includes system prompts, agent memory, and scaled output costs.

    Args:
        agents: List of agents used in the swarm
        input_text: The input task/prompt text
        execution_time: Time taken to execute in seconds
        agent_outputs: List of output texts from each agent or a list of dictionaries
        service_tier: The service tier being used ("standard" or "flex")

    Returns:
        Dict containing cost breakdown and total cost
    """
    # Base costs per unit (these could be moved to environment variables)
    COST_PER_AGENT = 0.01  # Base cost per agent
    COST_PER_1M_INPUT_TOKENS = 2.00  # Cost per 1M input tokens
    COST_PER_1M_OUTPUT_TOKENS = 4.50  # Cost per 1M output tokens

    # Flex processing discounts
    FLEX_INPUT_DISCOUNT = 0.25  # 75% discount for input tokens in flex mode
    FLEX_OUTPUT_DISCOUNT = 0.25  # 75% discount for output tokens in flex mode

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

        # Apply flex processing discounts if applicable
        if service_tier == "flex":
            input_token_cost *= FLEX_INPUT_DISCOUNT
            output_token_cost *= FLEX_OUTPUT_DISCOUNT

        # Apply night time discount
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
                "service_tier": service_tier,
                "night_time_discount_applied": is_night_time,
            },
            "total_cost": round(total_cost, 6),
        }

        return output

    except Exception as e:
        logger.error(f"Error calculating swarm cost: {str(e)}")
        raise ValueError(f"Failed to calculate swarm cost: {str(e)}")


def calculate_agent_cost(
    agent: Agent,
    input_text: str,
    execution_time: float,
    agent_output: Union[Dict[str, str], str, List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Calculate the cost for a single agent based on its input, output, and execution time.

    Args:
        agent: The agent instance
        input_text: The input task/prompt text
        execution_time: Time taken to execute in seconds
        agent_output: Output from the agent (can be dict, string, or list of dicts)

    Returns:
        Dict containing cost breakdown and total cost for this agent
    """
    # Base costs per unit
    COST_PER_AGENT = 0.01  # Base cost per agent
    COST_PER_1M_INPUT_TOKENS = 2.00  # Cost per 1M input tokens
    COST_PER_1M_OUTPUT_TOKENS = 4.50  # Cost per 1M output tokens

    # Get current time in California timezone
    california_tz = pytz.timezone("America/Los_Angeles")
    current_time = datetime.now(california_tz)
    is_night_time = current_time.hour >= 20 or current_time.hour < 6  # 8 PM to 6 AM

    try:
        # Calculate input tokens
        input_tokens = count_tokens(input_text)  # Base task tokens

        # Add system prompt tokens if present
        if agent.system_prompt:
            input_tokens += count_tokens(agent.system_prompt)

        # Add memory tokens if available
        try:
            memory = agent.short_memory.return_history_as_string()
            if memory:
                memory_tokens = count_tokens(str(memory))
                input_tokens += memory_tokens
        except Exception as e:
            logger.warning(
                f"Could not get memory for agent {agent.agent_name}: {str(e)}"
            )

        # Calculate output tokens
        if agent_output:
            if isinstance(agent_output, list):
                # Sum tokens for each dictionary's content
                output_tokens = sum(
                    count_tokens(message["content"]) for message in agent_output
                )
            elif isinstance(agent_output, str):
                output_tokens = count_tokens(agent_output)
            elif isinstance(agent_output, dict):
                output_tokens = count_tokens(any_to_str(agent_output))
            else:
                output_tokens = count_tokens(any_to_str(agent_output))
        else:
            output_tokens = int(input_tokens * 2.5)  # Estimated output tokens

        # Calculate base costs (convert to millions of tokens)
        agent_base_cost = COST_PER_AGENT
        input_token_cost = (input_tokens / 1_000_000) * COST_PER_1M_INPUT_TOKENS
        output_token_cost = (output_tokens / 1_000_000) * COST_PER_1M_OUTPUT_TOKENS

        # Apply discount during California night time hours
        if is_night_time:
            input_token_cost *= 0.25  # 75% discount
            output_token_cost *= 0.25  # 75% discount

        # Calculate total cost
        total_cost = agent_base_cost + input_token_cost + output_token_cost

        return {
            "agent_name": agent.agent_name,
            "cost_breakdown": {
                "agent_base_cost": round(agent_base_cost, 6),
                "input_token_cost": round(input_token_cost, 6),
                "output_token_cost": round(output_token_cost, 6),
                "token_counts": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
                "execution_time_seconds": round(execution_time, 2),
                "night_time_discount_applied": is_night_time,
            },
            "total_cost": round(total_cost, 6),
        }

    except Exception as e:
        logger.error(f"Error calculating agent cost: {str(e)}")
        raise ValueError(f"Failed to calculate agent cost: {str(e)}")


async def _run_agent_completion(
    agent_completion: AgentCompletion, x_api_key=Header(...)
) -> Dict[str, Any]:
    """
    Run an agent with the specified task.
    """
    try:
        current_time = time()

        # Check cache first
        cache_key = (
            f"{agent_completion.agent_config.model_dump_json()}_{agent_completion.task}"
        )
        if cache_key in agent_cache:
            cached_data = agent_cache[cache_key]
            if current_time - cached_data["timestamp"] <= CACHE_TTL:
                logger.debug("Returning cached agent result")
                return cached_data["response"]

        # Validate agent configuration
        if not agent_completion.agent_config.agent_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Agent name is required"
            )

        try:
            # Create agent from the config
            agent = Agent(
                **agent_completion.agent_config.model_dump(),
                output_type="dict-all-except-first",
            )
        except ValueError as ve:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid agent configuration: {str(ve)}",
            )

        try:
            # Run the agent with the provided task
            result = agent.run(task=agent_completion.task)
        except Exception as run_error:
            logger.error(f"Agent execution failed: {str(run_error)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Agent execution failed: {str(run_error)}",
            )

        # Generate a unique id
        try:
            unique_id = generate_key("agent")
        except Exception as key_error:
            logger.error(f"Failed to generate unique ID: {str(key_error)}")
            unique_id = str(uuid4())  # Fallback to UUID if key generation fails

        # Calculate tokens once and reuse
        input_text = agent_completion.task + agent.system_prompt + agent.name
        input_tokens = count_tokens(input_text)
        output_tokens = count_tokens(any_to_str(result))

        usage_data = {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

        output = {
            "id": unique_id,
            "success": True,
            "name": agent.name,
            "description": agent_completion.agent_config.description,
            "temperature": agent.temperature,
            "outputs": result,
            "usage": usage_data,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        # Cache the result
        agent_cache[cache_key] = {"response": output, "timestamp": current_time}

        # Clean up cache periodically
        if current_time % CACHE_CLEANUP_INTERVAL < 1:
            cleanup_agent_cache()

        try:
            log_api_request(api_key=x_api_key, data=output)
        except Exception as log_error:
            logger.error(f"Failed to log API request: {str(log_error)}")
            # Continue execution even if logging fails

        return output
    except HTTPException:
        # Re-raise HTTP exceptions as they're already properly formatted
        raise
    except Exception as e:
        logger.error(f"Unexpected error running agent: {str(e)}")
        logger.exception(e)  # Log full traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred: {str(e)}",
        )


def batched_agent_completion(
    agent_completions: List[AgentCompletion],
    x_api_key: str,
) -> List[Dict[str, Any]]:
    """
    Process multiple agent completions sequentially.

    Args:
        agent_completions (List[AgentCompletion]): List of agent completion tasks to process
        x_api_key (str): API key for authentication

    Returns:
        List[Dict[str, Any]]: List of results from completed agent tasks

    Raises:
        ValueError: If agent_completions is empty
        Exception: For any unexpected errors during batch processing
    """
    if not agent_completions:
        raise ValueError("No agent completions provided")

    try:
        processed_results = []
        for agent_completion in agent_completions:
            try:
                result = _run_agent_completion(agent_completion, x_api_key)
                processed_results.append(result)
            except Exception as e:
                logger.error(f"Error processing agent completion: {str(e)}")
                processed_results.append(
                    {
                        "success": False,
                        "error": str(e),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )

        return processed_results

    except Exception as e:
        logger.error(f"Failed to initialize batch processing: {str(e)}")
        raise Exception(f"Batch processing failed: {str(e)}")


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
        "start_timestamp": datetime.now(UTC).isoformat(),
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
                        "timestamp": datetime.now(UTC).isoformat(),
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
                        "timestamp": datetime.now(UTC).isoformat(),
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
async def check_swarm_types() -> Dict[Any, Any]:
    """
    Check the available swarm types.
    """

    # Await
    swarm_types = await get_swarm_types()

    out = {
        "success": True,
        "swarm_types": swarm_types,
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
    try:

        return await run_swarm_completion(swarm, x_api_key)
    except Exception as e:
        logger.error(f"Error running swarm: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


# Cache for agent configurations and results
agent_cache = {}
CACHE_TTL = 300  # 5 minutes
CACHE_CLEANUP_INTERVAL = 60  # 1 minute


def cleanup_agent_cache():
    """Clean up expired cache entries"""
    current_time = time()
    expired_keys = [
        k for k, v in agent_cache.items() if current_time - v["timestamp"] > CACHE_TTL
    ]
    for k in expired_keys:
        del agent_cache[k]


@app.post(
    "/v1/agent/completions",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
async def run_agent(
    agent_completion: AgentCompletion, x_api_key=Header(...)
) -> Dict[str, Any]:
    """
    Run an agent with the specified task.
    """
    try:
        return await _run_agent_completion(agent_completion, x_api_key)
    except Exception as e:
        logger.error(f"Error running agent: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@app.post(
    "/v1/agent/batch/completions",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
async def run_agent_batch(
    agent_completions: List[AgentCompletion], x_api_key=Header(...)
) -> List[Dict[str, Any]]:
    """
    Run a batch of agents with the specified tasks using a thread pool.

    Args:
        agent_completions: List of agent completion tasks to process
        x_api_key: API key for authentication

    Returns:
        List[Dict[str, Any]]: List of results from completed agent tasks

    Raises:
        HTTPException: If there's an error processing the batch
    """
    if not agent_completions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No agent completions provided",
        )

    try:
        logger.info(f"Running batch of {len(agent_completions)} agents")

        # Process logging concurrently with the main task
        async def log_request():
            try:
                await log_api_request(x_api_key, agent_completions)
            except Exception as log_error:
                logger.warning(f"Failed to log incoming request: {str(log_error)}")

        # Start logging in background
        log_task = asyncio.create_task(log_request())

        # Process the batch with optimized concurrency
        results = await batched_agent_completion(agent_completions, x_api_key)

        # Wait for logging to complete
        await log_task

        # Log results in background without waiting
        asyncio.create_task(log_api_request(x_api_key, results))

        logger.info(f"Successfully completed batch of {len(results)} agents")
        return results

    except Exception as e:
        logger.error(f"Error running agent batch: {str(e)}")
        logger.exception(e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process agent batch: {str(e)}",
        )


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
        return {
            "status": "success",
            "count": len(logs),
            "logs": logs,
            "timestamp": datetime.now(UTC).isoformat(),
        }
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


# --- Main Entrypoint ---

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080, reload=True)

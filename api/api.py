import asyncio
import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from threading import Thread
from time import sleep, time
from typing import Any, Dict, List, Optional, Union

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
from loguru import logger
from pydantic import BaseModel, Field
from swarms import Agent, SwarmRouter, SwarmType
from swarms.agents.reasoning_agents import OutputType, agent_types
from swarms.utils.litellm_tokenizer import count_tokens

load_dotenv()

# Define rate limit parameters
RATE_LIMIT = 100  # Max requests
TIME_WINDOW = 60  # Time window in seconds

# In-memory store for tracking requests
request_counts = defaultdict(lambda: {"count": 0, "start_time": time()})

# In-memory store for scheduled jobs
scheduled_jobs: Dict[str, Dict] = {}


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
        None,
        description="The unique name assigned to the agent, which identifies its role and functionality within the swarm.",
    )
    description: Optional[str] = Field(
        None,
        description="A detailed explanation of the agent's purpose, capabilities, and any specific tasks it is designed to perform.",
    )
    system_prompt: Optional[str] = Field(
        None,
        description="The initial instruction or context provided to the agent, guiding its behavior and responses during execution.",
    )
    model_name: Optional[str] = Field(
        description="The name of the AI model that the agent will utilize for processing tasks and generating outputs. For example: gpt-4o, gpt-4o-mini, openai/o3-mini"
    )
    auto_generate_prompt: Optional[bool] = Field(
        description="A flag indicating whether the agent should automatically create prompts based on the task requirements."
    )
    max_tokens: Optional[int] = Field(
        None,
        description="The maximum number of tokens that the agent is allowed to generate in its responses, limiting output length.",
    )
    temperature: Optional[float] = Field(
        description="A parameter that controls the randomness of the agent's output; lower values result in more deterministic responses."
    )
    role: Optional[str] = Field(
        description="The designated role of the agent within the swarm, which influences its behavior and interaction with other agents."
    )
    max_loops: Optional[int] = Field(
        description="The maximum number of times the agent is allowed to repeat its task, enabling iterative processing if necessary."
    )
    # tools: Optional[List[Any]] = Field(
    #     description="A list of tools that the agent can use to complete its task."
    # )
    tools_dictionary: Optional[Dict[str, Any]] = Field(
        description="A dictionary of tools that the agent can use to complete its task."
    )


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


class ReasoningAgentSpec(BaseModel):
    agent_name: str = Field(
        "reasoning_agent",
        description="The name of the reasoning agent, which identifies its role and functionality within the swarm.",
    )
    description: str = Field(
        "A reasoning agent that can answer questions and help with tasks.",
        description="A detailed explanation of the agent's purpose, capabilities, and any specific tasks it is designed to perform.",
    )
    model_name: str = Field(
        "gpt-4o-mini",
        description="The name of the AI model that the agent will utilize for processing tasks and generating outputs. For example: gpt-4o, gpt-4o-mini, openai/o3-mini",
    )
    system_prompt: str = Field(
        "You are a helpful assistant that can answer questions and help with tasks.",
        description="The initial instruction or context provided to the agent, guiding its behavior and responses during execution.",
    )
    max_loops: int = Field(
        1,
        description="The maximum number of times the agent is allowed to repeat its task, enabling iterative processing if necessary.",
    )
    swarm_type: agent_types = Field(
        "reasoning_duo",
        description="The type of reasoning swarm to use (e.g., reasoning duo, self-consistency, IRE).",
    )
    num_samples: int = Field(
        1, description="The number of samples to generate for self-consistency agents."
    )
    output_type: OutputType = Field(
        "dict", description="The format of the output (e.g., dict, list)."
    )

    task: str = Field(
        None,
        description="The specific task or objective that the swarm is designed to accomplish.",
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
        None,
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


def create_swarm(swarm_spec: SwarmSpec, api_key: str):
    try:

        if swarm_spec.task is None and swarm_spec.tasks is None:
            logger.error("Swarm creation failed: 'task' field is missing.")
            raise HTTPException(
                status_code=400,
                detail="The 'task' field is mandatory for swarm creation. Please provide a valid task description to proceed.",
            )

        # Validate swarm_spec
        if not swarm_spec.agents or len(swarm_spec.agents) == 0:
            logger.info(
                "No agents specified. Auto-creating agents for task: {}",
                swarm_spec.task,
            )

            raise HTTPException(
                status_code=400,
                detail=f"No agents specified. Auto-creating agents for task: {swarm_spec.task}",
            )
        else:
            agents = []
            for agent_spec in swarm_spec.agents:
                try:
                    # Handle both dict and AgentSpec objects
                    if isinstance(agent_spec, dict):
                        agent_spec = AgentSpec(**agent_spec)

                    # Validate agent_spec fields
                    if not agent_spec.agent_name:
                        logger.error("Agent creation failed: Agent name is required.")
                        raise ValueError("Agent name is required.")
                    if not agent_spec.model_name:
                        logger.error("Agent creation failed: Model name is required.")
                        raise ValueError("Model name is required.")

                    # Create the agent
                    agent = Agent(
                        agent_name=agent_spec.agent_name,
                        description=agent_spec.description,
                        system_prompt=agent_spec.system_prompt,
                        model_name=agent_spec.model_name or "gpt-4o",
                        auto_generate_prompt=agent_spec.auto_generate_prompt or False,
                        max_tokens=agent_spec.max_tokens or 8192,
                        temperature=agent_spec.temperature or 0.5,
                        role=agent_spec.role or "worker",
                        max_loops=agent_spec.max_loops or 1,
                        dynamic_temperature_enabled=True,
                        tools_list_dictionary=agent_spec.tools_dictionary,
                    )

                    agents.append(agent)
                    logger.info("Successfully created agent: {}", agent_spec.agent_name)
                except ValueError as ve:
                    logger.error(
                        "Validation error for agent {}: {}",
                        getattr(agent_spec, "agent_name", "unknown"),
                        str(ve),
                    )
                    raise
                except Exception as agent_error:
                    logger.error(
                        "Error creating agent {}: {}",
                        getattr(agent_spec, "agent_name", "unknown"),
                        str(agent_error),
                    )
                    raise

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

        # Calculate costs
        start_time = time()

        # Run the swarm task

        if swarm_spec.tasks is not None:
            output = swarm.batch_run(tasks=swarm_spec.tasks)
        else:
            output = swarm.run(task=swarm_spec.task)

        # Calculate execution time
        execution_time = time() - start_time

        # Calculate costs
        cost_info = calculate_swarm_cost(
            agents=agents,
            input_text=swarm_spec.task,
            execution_time=execution_time,
            agent_outputs=output,
        )

        print(cost_info)

        deduct_credits(
            api_key,
            cost_info["total_cost"],
            f"swarm_execution_{swarm_spec.name}",
        )

        logger.info("Swarm task executed successfully: {}", swarm_spec.task)
        return output
    except HTTPException as http_exc:
        logger.error("HTTPException occurred while creating swarm: {}", http_exc.detail)
        raise
    except Exception as e:
        logger.error("Error creating swarm: {}", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create swarm: {str(e)}",
        )


# Add this function after your get_supabase_client() function
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

        agents = swarm.agents

        await log_api_request(x_api_key, swarm.model_dump())

        # Log start of swarm execution
        logger.info(f"Starting swarm {swarm_name} with {len(agents)} agents")

        # Create and run the swarm
        logger.debug(f"Creating swarm object for {swarm_name}")

        start_time = time()
        result = create_swarm(swarm, x_api_key)
        logger.debug(f"Running swarm task: {swarm.task}")

        # Format the response
        response = {
            "status": "success",
            "swarm_name": swarm_name,
            "description": swarm.description,
            "swarm_type": swarm.swarm_type,
            "task": swarm.task,
            "output": result,
            "number_of_agents": len(agents),
            "input_config": swarm.model_dump(),
        }
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


# def create_reasoning_agent(reasoning_agent_spec: ReasoningAgentSpec, api_key: str):
#     logger.info("Creating reasoning agent: {}", reasoning_agent_spec.agent_name)

#     # Validate task field
#     if reasoning_agent_spec.task is None:
#         logger.error("Reasoning agent creation failed: 'task' field is missing.")
#         raise HTTPException(
#             status_code=400,
#             detail="The 'task' field is mandatory for reasoning agent creation. Please provide a valid task description to proceed.",
#         )

#     try:
#         log_api_request(api_key, reasoning_agent_spec.model_dump())

#         reasoning_agent = ReasoningAgentRouter(
#             agent_name=reasoning_agent_spec.agent_name,
#             description=reasoning_agent_spec.description,
#             model_name=reasoning_agent_spec.model_name,
#             system_prompt=reasoning_agent_spec.system_prompt,
#             max_loops=reasoning_agent_spec.max_loops,
#             swarm_type=reasoning_agent_spec.swarm_type,
#             num_samples=reasoning_agent_spec.num_samples,
#             output_type="dict",
#         )

#         logger.debug("Running reasoning agent task: {}", reasoning_agent_spec.task)

#         start_time = time()

#         output = reasoning_agent.run(reasoning_agent_spec.task)

#         print(output)

#         # Calculate costs
#         cost_info = calculate_swarm_cost(
#             agents=[reasoning_agent],
#             input_text=reasoning_agent_spec.task,
#             execution_time=time() - start_time,
#             agent_outputs=any_to_str(output),
#         )

#         # print(cost_info)

#         deduct_credits(
#             api_key,
#             cost_info["total_cost"],
#             f"reasoning_agent_{reasoning_agent_spec.agent_name}: Agent type {reasoning_agent_spec.swarm_type}",
#         )

#         if output is None:
#             raise HTTPException(
#                 status_code=400,
#                 detail="The reasoning agent returned no output. Please try again.",
#             )

#         result = {
#             "status": "success",
#             "agent-name": reasoning_agent_spec.agent_name,
#             "agent-description": reasoning_agent_spec.description,
#             "agent-type": reasoning_agent_spec.swarm_type,
#             "outputs": output,
#             "input_config": reasoning_agent_spec.model_dump(),
#             "costs": cost_info,
#         }

#         log_api_request(api_key, result)
#         logger.info(
#             "Successfully created reasoning agent: {}", reasoning_agent_spec.agent_name
#         )

#         return result

#     except Exception as e:
#         logger.error(
#             "Error creating reasoning agent {}: {}",
#             reasoning_agent_spec.agent_name,
#             str(e),
#         )
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to create reasoning agent: {e}",
#         )


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
            detail="Insufficient credits.",
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
    agents: List[Agent],
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
                else:
                    agent_output_tokens = int(
                        agent_input_tokens * 2.5
                    )  # Estimated output tokens
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


def get_swarm_types():
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


@app.get("/", dependencies=[Depends(rate_limiter)])
def root():
    return {
        "status": "Welcome to the Swarm API. Check out the docs at https://docs.swarms.world"
    }


@app.get("/health", dependencies=[Depends(rate_limiter)])
def health():
    return {"status": "ok"}


@app.get(
    "/v1/swarms/available",
    dependencies=[
        Depends(rate_limiter),
    ],
)
async def check_swarm_types() -> List[str]:
    """
    Check the available swarm types.
    """
    return get_swarm_types()


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
    return await run_swarm_completion(swarm, x_api_key)


# @app.post(
#     "/v1/agent/completions",
#     dependencies=[Depends(verify_api_key), Depends(rate_limiter)],
# )
# def run_agent(agent: ReasoningAgentSpec, x_api_key=Header(...)) -> Dict[str, Any]:
#     """
#     Run an agent with the specified task.
#     """
#     return create_reasoning_agent(agent, x_api_key)


@app.post(
    "/v1/swarm/batch/completions",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
async def run_batch_completions(
    swarms: List[SwarmSpec], x_api_key=Header(...)
) -> List[Dict[str, Any]]:
    """
    Run a batch of swarms with the specified tasks.
    """
    results = []
    for swarm in swarms:
        try:
            # Call the existing run_swarm function for each swarm
            result = await run_swarm_completion(swarm, x_api_key)
            results.append(result)
        except HTTPException as http_exc:
            logger.error("HTTPException occurred: {}", http_exc.detail)
            results.append(
                {
                    "status": "error",
                    "swarm_name": swarm.name,
                    "detail": http_exc.detail,
                }
            )
        except Exception as e:
            logger.error("Error running swarm {}: {}", swarm.name, str(e))
            logger.exception(e)
            results.append(
                {
                    "status": "error",
                    "swarm_name": swarm.name,
                    "detail": f"Failed to run swarm: {str(e)}",
                }
            )

    return results


@app.get(
    "/v1/swarms/available",
    dependencies=[
        Depends(verify_api_key),
        Depends(rate_limiter),
    ],
)
async def get_available_swarms(x_api_key: str = Header(...)) -> Dict[str, Any]:
    """
    Get all available swarms.
    """
    available_swarms = await SwarmType
    print(available_swarms)  # Print the list of available swarms
    return available_swarms


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

    uvicorn.run(app, host="0.0.0.0", port=8080, workers=os.cpu_count())

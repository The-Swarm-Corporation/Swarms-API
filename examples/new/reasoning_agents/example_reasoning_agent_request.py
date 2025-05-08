import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from functools import lru_cache
from time import time
from typing import Any, Dict, List, Optional, Union

import pytz
import supabase
from dotenv import load_dotenv
from fastapi import (
    Header,
    HTTPException,
    Request,
    status,
)
from loguru import logger
from pydantic import BaseModel, Field
from swarms import Agent
from swarms.agents.reasoning_agents import ReasoningAgentRouter, agent_types, OutputType
from swarms.utils.litellm_tokenizer import count_tokens
import json
from swarms.utils.any_to_str import any_to_str

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
    agent_outputs: Union[
        List[Dict[str, str]], str, Dict, List
    ] = None,  # Update agent_outputs type
) -> Dict[str, Any]:
    """
    Calculate the cost of running a swarm based on agents, tokens, and execution time.
    Includes system prompts, agent memory, and scaled output costs.

    Args:
        agents: List of agents used in the swarm
        input_text: The input task/prompt text
        execution_time: Time taken to execute in seconds
        agent_outputs: Output from agents in various formats

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
            if agent_outputs is not None:
                try:
                    if isinstance(agent_outputs, str):
                        agent_output_tokens = count_tokens(agent_outputs)
                    elif isinstance(agent_outputs, dict):
                        # Convert dict to string for token counting
                        agent_output_tokens = count_tokens(str(agent_outputs))
                    elif isinstance(agent_outputs, list):
                        # Handle list of dicts with "content" field
                        if all(
                            isinstance(item, dict) and "content" in item
                            for item in agent_outputs
                        ):
                            agent_output_tokens = sum(
                                count_tokens(message["content"])
                                for message in agent_outputs
                            )
                        else:
                            # Convert list to string for token counting
                            agent_output_tokens = count_tokens(str(agent_outputs))
                    else:
                        # Fallback for other types
                        agent_output_tokens = count_tokens(str(agent_outputs))
                except Exception as e:
                    logger.warning(f"Error counting output tokens: {str(e)}")
                    agent_output_tokens = int(
                        agent_input_tokens * 2.5
                    )  # Fallback estimate
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


def create_reasoning_agent(reasoning_agent_spec: ReasoningAgentSpec, api_key: str):
    logger.info("Creating reasoning agent: {}", reasoning_agent_spec.agent_name)

    # Validate task field
    if reasoning_agent_spec.task is None:
        logger.error("Reasoning agent creation failed: 'task' field is missing.")
        raise HTTPException(
            status_code=400,
            detail="The 'task' field is mandatory for reasoning agent creation. Please provide a valid task description to proceed.",
        )

    try:
        log_api_request(api_key, reasoning_agent_spec.model_dump())

        reasoning_agent = ReasoningAgentRouter(
            agent_name=reasoning_agent_spec.agent_name,
            description=reasoning_agent_spec.description,
            model_name=reasoning_agent_spec.model_name,
            system_prompt=reasoning_agent_spec.system_prompt,
            max_loops=reasoning_agent_spec.max_loops,
            swarm_type=reasoning_agent_spec.swarm_type,
            num_samples=reasoning_agent_spec.num_samples,
            output_type="dict",
        )

        logger.debug("Running reasoning agent task: {}", reasoning_agent_spec.task)

        start_time = time()

        output = reasoning_agent.run(reasoning_agent_spec.task)

        print(output)

        # Calculate costs
        cost_info = calculate_swarm_cost(
            agents=[reasoning_agent],
            input_text=reasoning_agent_spec.task,
            execution_time=time() - start_time,
            agent_outputs=any_to_str(output),
        )

        # print(cost_info)

        deduct_credits(
            api_key,
            cost_info["total_cost"],
            f"reasoning_agent_{reasoning_agent_spec.agent_name}: Agent type {reasoning_agent_spec.swarm_type}",
        )

        if output is None:
            raise HTTPException(
                status_code=400,
                detail="The reasoning agent returned no output. Please try again.",
            )

        result = {
            "status": "success",
            "agent-name": reasoning_agent_spec.agent_name,
            "agent-description": reasoning_agent_spec.description,
            "agent-type": reasoning_agent_spec.swarm_type,
            "outputs": output,
            "input_config": reasoning_agent_spec.model_dump(),
            "costs": cost_info,
        }

        log_api_request(api_key, result)
        logger.info(
            "Successfully created reasoning agent: {}", reasoning_agent_spec.agent_name
        )

        return result

    except Exception as e:
        logger.error(
            "Error creating reasoning agent {}: {}",
            reasoning_agent_spec.agent_name,
            str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create reasoning agent: {e}",
        )


config = ReasoningAgentSpec(
    agent_name="reasoning_agent",
    description="A reasoning agent that can answer questions and help with tasks.",
    model_name="gpt-4o-mini",
    system_prompt="You are a helpful assistant that can answer questions and help with tasks.",
    max_loops=1,
    swarm_type="self-consistency",
    num_samples=1,
    output_type="dict",
    task="What is the capital of the moon?",
)


out = create_reasoning_agent(config, os.getenv("SWARMS_API_KEY"))
print(json.dumps(out, indent=4))

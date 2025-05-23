# tools - search, code executor, create api

import os
import aiohttp
import asyncio
from dotenv import load_dotenv
import json
from swarms.utils.formatter import formatter

load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://swarms-api-285321057562.us-east1.run.app"
# BASE_URL = "https://api.swarms.world"

headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


async def run_batch_agents(payloads):
    """Run multiple agents in batch with the AgentCompletion format

    Args:
        payloads (list): List of payload dictionaries, each containing agent_config and task

    Returns:
        list: List of responses from each agent
    """
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{BASE_URL}/v1/agent/batch/completions", headers=headers, json=payloads
            ) as response:
                response.raise_for_status()
                return await response.json()
    except aiohttp.ClientError as e:
        print(f"Error making batch request: {e}")
        return None


async def main():
    # Example batch payloads
    batch_payloads = [
        {
            "agent_config": {
                "agent_name": "Research Analyst",
                "description": "An expert in analyzing and synthesizing research data",
                "system_prompt": (
                    "You are a Research Analyst with expertise in data analysis and synthesis. "
                    "Your role is to analyze provided information, identify key insights, "
                    "and present findings in a clear, structured format. "
                    "Focus on accuracy, clarity, and actionable recommendations."
                ),
                "model_name": "gpt-4",
                "role": "worker",
                "max_loops": 2,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            "task": "Analyze the impact of artificial intelligence on healthcare delivery and provide a comprehensive report with key findings and recommendations.",
        },
        {
            "agent_config": {
                "agent_name": "Market Analyst",
                "description": "An expert in market analysis and trends",
                "system_prompt": (
                    "You are a Market Analyst with deep knowledge of market trends and analysis. "
                    "Your role is to evaluate market conditions, identify opportunities, "
                    "and provide strategic insights for business decisions."
                ),
                "model_name": "gpt-4",
                "role": "worker",
                "max_loops": 2,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            "task": "Analyze the current market trends in the AI industry and provide strategic recommendations for businesses looking to enter this space.",
        },
    ]

    # Run batch agents
    print("Running Batch Agents:")
    batch_results = await run_batch_agents(batch_payloads)
    if batch_results:
        formatter.print_panel(json.dumps(batch_results, indent=4))


if __name__ == "__main__":
    asyncio.run(main())

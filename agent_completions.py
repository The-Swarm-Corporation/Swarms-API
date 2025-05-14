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


async def run_health_check(session):
    """Check if the API is healthy"""
    async with session.get(f"{BASE_URL}/health", headers=headers) as response:
        return await response.json()


async def run_single_agent(session):
    """Run a single agent with the new AgentCompletion format"""
    payload = {
        "agent_config": {
            "agent_name": "Research Analyst",
            "description": "An expert in analyzing and synthesizing research data",
            "system_prompt": (
                "You are a Research Analyst with expertise in data analysis and synthesis. "
                "Your role is to analyze provided information, identify key insights, "
                "and present findings in a clear, structured format. "
                "Focus on accuracy, clarity, and actionable recommendations."
            ),
            "model_name": "gpt-4o",
            "role": "worker",
            "max_loops": 2,
            "max_tokens": 8192,
            "temperature": 0.5,
            "auto_generate_prompt": False,
        },
        "task": "Analyze the impact of artificial intelligence on healthcare delivery and provide a comprehensive report with key findings and recommendations.",
    }

    try:
        async with session.post(
            f"{BASE_URL}/v1/agent/completions", headers=headers, json=payload
        ) as response:
            response.raise_for_status()
            return await response.json()
    except aiohttp.ClientError as e:
        print(f"Error making request: {e}")
        return None


async def main():
    async with aiohttp.ClientSession() as session:
        # Check API health
        health = await run_health_check(session)
        print("API Health Check:")
        formatter.print_panel(json.dumps(health, indent=4))
        print("\n" + "=" * 50 + "\n")

        # Run single agent
        print("Running Single Agent:")
        agent_result = await run_single_agent(session)
        if agent_result:
            formatter.print_panel(json.dumps(agent_result, indent=4))
        print("\n" + "=" * 50 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

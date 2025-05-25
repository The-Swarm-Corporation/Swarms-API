import os
import aiohttp
import asyncio
from dotenv import load_dotenv
import json

load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://swarms-api-285321057562.us-east1.run.app"
headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


async def run_batch_agents(payloads):
    """Run multiple agents in batch"""
    if not payloads:
        raise ValueError("No payloads provided")

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/v1/agent/batch/completions",
            headers=headers,
            json=payloads,
            timeout=300,
        ) as response:
            if response.status != 200:
                raise Exception(f"API request failed: {response.status}")
            return await response.json()


async def main():
    # Example payload
    payload = {
        "agent_config": {
            "agent_name": "Research Analyst",
            "system_prompt": "You are a Research Analyst. Analyze the given information and provide insights.",
            "model_name": "gpt-4",
            "max_tokens": 8192,
            "temperature": 0.5,
        },
        "task": "Analyze the impact of AI on healthcare.",
    }

    try:
        results = await run_batch_agents([payload])
        print(json.dumps(results, indent=2))
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())

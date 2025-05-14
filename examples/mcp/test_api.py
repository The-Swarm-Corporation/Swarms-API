import asyncio
from fastmcp import Client

swarm_config = {
    "name": "Simple Financial Analysis",
    "description": "A swarm to analyze financial data",
    "agents": [
        {
            "agent_name": "Data Analyzer",
            "description": "Looks at financial data",
            "system_prompt": "Analyze the data.",
            "model_name": "gpt-4o",
            "role": "worker",
            "max_loops": 1,
            "max_tokens": 1000,
            "temperature": 0.5,
            "auto_generate_prompt": False,
        },
        {
            "agent_name": "Risk Analyst",
            "description": "Checks risk levels",
            "system_prompt": "Evaluate the risks.",
            "model_name": "gpt-4o",
            "role": "worker",
            "max_loops": 1,
            "max_tokens": 1000,
            "temperature": 0.5,
            "auto_generate_prompt": False,
        },
        {
            "agent_name": "Strategy Checker",
            "description": "Validates strategies",
            "system_prompt": "Review the strategy.",
            "model_name": "gpt-4o",
            "role": "worker",
            "max_loops": 1,
            "max_tokens": 1000,
            "temperature": 0.5,
            "auto_generate_prompt": False,
        },
    ],
    "max_loops": 1,
    "swarm_type": "SequentialWorkflow",
    "task": "Analyze the financial data and provide insights.",
    "return_history": False,  # Added required field
    "stream": False,  # Added required field
    "rules": None,  # Added optional field
    "img": None,  # Added optional field
}


async def fetch_weather_and_resource():
    """Connect to a server over SSE and fetch available swarms."""

    async with Client(
        transport="http://localhost:8000/sse"
        # SSETransport(
        #     url="http://localhost:8000/sse",
        #     headers={"x_api_key": os.getenv("SWARMS_API_KEY"), "Content-Type": "application/json"}
        # )
    ) as client:
        # Basic connectivity testing
        # print("Ping check:", await client.ping())
        # print("Available tools:", await client.list_tools())
        # print("Swarms available:", await client.call_tool("swarms_available", None))
        result = await client.call_tool("swarm_completion", {"swarm": swarm_config})
        print("Swarm completion:", result)


# Execute the function
if __name__ == "__main__":
    asyncio.run(fetch_weather_and_resource())

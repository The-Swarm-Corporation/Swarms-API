import asyncio
from swarms_client import SwarmClient, SwarmRequest, Agent


async def main():
    # Initialize the client
    async with SwarmClient() as client:
        # Check API health
        health = await client.health_check()
        print(f"API Status: {health.status}")

        # Create a single swarm
        swarm_request = SwarmRequest(
            name="Test Swarm",
            description="A test swarm",
            agents=[
                Agent(
                    agent_name="Research Agent",
                    description="Conducts research",
                    system_prompt="You are a research assistant.",
                    model_name="gpt-4",
                    max_loops=1,
                ),
                Agent(
                    agent_name="Writing Agent",
                    description="Writes content",
                    system_prompt="You are a content writer.",
                    model_name="gpt-4",
                    max_loops=1,
                ),
            ],
            max_loops=1,
            swarm_type="ConcurrentWorkflow",
            task="Write a short blog post about AI agents.",
        )

        response = await client.create_swarm(swarm_request)
        print(f"Swarm Result: {response.result}")

        # Create batch swarms
        batch_requests = [
            SwarmRequest(
                name=f"Batch Swarm {i}",
                description=f"Swarm {i} in batch",
                agents=[
                    Agent(
                        agent_name="Worker Agent",
                        description="Does work",
                        system_prompt="You are a worker.",
                        model_name="gpt-4",
                        max_loops=1,
                    )
                ],
                max_loops=1,
                swarm_type="SequentialWorkflow",
                task=f"Task {i}",
            )
            for i in range(2)
        ]

        batch_responses = await client.create_batch_swarms(batch_requests)
        for i, response in enumerate(batch_responses):
            print(f"Batch Swarm {i} Result: {response.result}")


if __name__ == "__main__":
    asyncio.run(main())

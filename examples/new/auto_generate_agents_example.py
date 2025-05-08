from swarms.structs.agent_builder import AgentsBuilder
from dotenv import load_dotenv

load_dotenv()

swarm = AgentsBuilder()

print(
    swarm.run(
        task="Create a comprehensive market analysis report for AI companies, including financial metrics, growth potential, and competitive analysis."
    )
)

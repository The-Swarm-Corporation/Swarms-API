import json
import os

import requests
from dotenv import load_dotenv

load_dotenv()

# Base URL for local testing
BASE_URL = "https://api.swarms.world"

# Test API key - you'll need to replace this with a valid key
API_KEY = os.getenv("SWARMS_API_KEY")

# Headers used for all requests
headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def test_batch_swarm():
    """Test the batch swarm completions endpoint"""
    payload = [
        {
            "name": "Batch Swarm 1",
            "description": "First swarm in the batch",
            "agents": [
                {
                    "agent_name": "Research Agent",
                    "description": "Conducts research",
                    "system_prompt": "You are a research assistant.",
                    "model_name": "gpt-4",
                    "role": "worker",
                    "max_loops": 1,
                },
                {
                    "agent_name": "Analysis Agent",
                    "description": "Analyzes data",
                    "system_prompt": "You are a data analyst.",
                    "model_name": "gpt-4",
                    "role": "worker",
                    "max_loops": 1,
                },
            ],
            "max_loops": 1,
            "swarm_type": "SequentialWorkflow",
            "task": "Research AI advancements.",
        },
        {
            "name": "Batch Swarm 2",
            "description": "Second swarm in the batch",
            "agents": [
                {
                    "agent_name": "Writing Agent",
                    "description": "Writes content",
                    "system_prompt": "You are a content writer.",
                    "model_name": "gpt-4",
                    "role": "worker",
                    "max_loops": 1,
                },
                {
                    "agent_name": "Editing Agent",
                    "description": "Edits content",
                    "system_prompt": "You are an editor.",
                    "model_name": "gpt-4",
                    "role": "worker",
                    "max_loops": 1,
                },
            ],
            "max_loops": 1,
            "swarm_type": "SequentialWorkflow",
            "task": "Write a summary of AI research.",
        },
    ]

    print("\n=== Batch Swarm Test ===")
    try:
        response = requests.post(
            f"{BASE_URL}/v1/swarm/batch/completions",
            headers=headers,
            json=payload,
            timeout=300,
        )
        response.raise_for_status()

        print(f"Status Code: {response.status_code}")
        print(f"Processing {len(payload)} swarms...")

        result = response.json()

        for idx, swarm_result in enumerate(result, 1):
            print(f"\nSwarm {idx} Status: {swarm_result.get('status', 'Unknown')}")
            if "error" in swarm_result:
                print(f"Error in Swarm {idx}: {swarm_result['error']}")

        return json.dumps(result, indent=4)

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Error processing batch request: {str(e)}")
        return json.dumps({"error": str(e)}, indent=4)


test_batch_swarm()

import os
import requests
import json


API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://swarms-api-285321057562.us-east1.run.app"

headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


# Request body
payload = {
    "agent_name": "reasoning-agent",
    "description": "A reasoning agent that can solve complex problems",
    "model_name": "gpt-4o-mini",
    "system_prompt": "You are a helpful reasoning agent that can solve complex problems.",
    "max_loops": 1,
    "swarm_type": "AgentJudge",
    "num_samples": 1,
    "output_type": "dict",
    "num_knowledge_items": 1,
    "memory_capacity": 1,
    "task": "What is the capital of France?",
}

try:
    # Make the POST request
    response = requests.post(
        f"{BASE_URL}/v1/agents/completions", headers=headers, json=payload
    )

    # Check if the request was successful
    if response.status_code == 200:
        print("Request successful!")
        print("Response:", json.dumps(response.json(), indent=2))
    else:
        print(f"Request failed with status code: {response.status_code}")
        print("Response:", response.text)

except Exception as e:
    print(f"An error occurred: {str(e)}")

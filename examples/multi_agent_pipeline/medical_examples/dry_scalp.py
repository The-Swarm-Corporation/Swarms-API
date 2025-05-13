# tools - search, code executor, create api

import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://api.swarms.world"

headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def run_health_check():
    response = requests.get(f"{BASE_URL}/health", headers=headers)
    return response.json()


def run_single_swarm():
    payload = {
        "name": "Hair Care Product Analysis Swarm",
        "description": "Analyzes and recommends hair care products based on user needs.",
        "agents": [
            {
                "agent_name": "Hair Product Specialist",
                "description": "Expert in hair care products and their benefits.",
                "system_prompt": "You are a hair care product specialist with extensive knowledge of ingredients and their effects on different hair types.",
                "model_name": "gpt-4o-mini",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
                "tools_dictionary": [],
            },
            {
                "agent_name": "Hair Health Advisor",
                "description": "Provides personalized hair care advice and product recommendations.",
                "system_prompt": "You are a hair health advisor who understands various hair concerns and can suggest suitable products.",
                "model_name": "gpt-4o-mini",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
                "tools_dictionary": [],
            },
        ],
        "max_loops": 1,
        "swarm_type": "ConcurrentWorkflow",
        "task": "What are the best hair care products for dry and damaged hair? Provide a list of the best products and their benefits.",
        "output_type": "dict",
    }

    response = requests.post(
        f"{BASE_URL}/v1/swarm/completions",
        headers=headers,
        json=payload,
    )

    print(response)
    print(response.status_code)
    # return response.json()
    output = response.json()

    return json.dumps(output, indent=4)


def get_logs():
    response = requests.get(f"{BASE_URL}/v1/swarm/logs", headers=headers)
    output = response.json()
    # return json.dumps(output, indent=4)
    return output


def get_swarm_types():
    response = requests.get(f"{BASE_URL}/v1/swarms/available")
    print(response)
    return response.json()


if __name__ == "__main__":
    result = run_single_swarm()
    print("Swarm Result:")
    print(result)

    # swarm_types = get_swarm_types()
    # print("Swarm Types:")
    # print(swarm_types)

    # logs = get_logs()
    # logs = json.dumps(logs, indent=4)
    # print("Logs:")

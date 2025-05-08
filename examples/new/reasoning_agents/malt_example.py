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
        "name": "Financial Analysis Swarm",
        "description": "Market analysis swarm",
        "max_loops": 1,
        "swarm_type": "MALT",
        "task": "Create a thesis solving the pnp problem",
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

import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://swarms-api-285321057562.us-east1.run.app"

headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def auto_generate_agents():
    """Test the auto-generate agents endpoint"""
    payload = {
        "task": "Create a comprehensive market analysis report for AI companies, including financial metrics, growth potential, and competitive analysis."
    }

    response = requests.post(
        f"{BASE_URL}/v1/agents/auto-generate",
        headers=headers,
        json=payload,
    )

    print(f"Status Code: {response.status_code}")

    try:
        output = response.json()
        return json.dumps(output, indent=4)
    except json.JSONDecodeError as e:
        print(f"Error decoding response: {e}")
        return response.text


if __name__ == "__main__":
    print("Testing Auto-Generate Agents:")
    result = auto_generate_agents()
    print(result)

    # Comment out or remove the other test calls if you want to focus on this test
    # result = run_single_swarm()
    # print("Swarm Result:")
    # print(result)

    # swarm_types = get_swarm_types()
    # print("Swarm Types:")
    # print(swarm_types)

    # logs = get_logs()
    # logs = json.dumps(logs, indent=4)
    # print("Logs:")

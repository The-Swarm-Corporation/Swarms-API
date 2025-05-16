import os
import requests
from dotenv import load_dotenv
import json
from swarms.utils.formatter import formatter

load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://swarms-api-285321057562.us-east1.run.app"
# BASE_URL = "http://localhost:8080"


headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def fetch_logs():
    """Fetch logs for a specific agent"""
    url = f"{BASE_URL}/v1/swarm/logs"
    response = requests.get(url, headers=headers)
    return response.json()


if __name__ == "__main__":
    logs = fetch_logs()
    formatter.print_panel(json.dumps(logs, indent=4))

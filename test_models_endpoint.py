# tools - search, code executor, create api

import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://api.swarms.world"

headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def get_models():
    response = requests.get(f"{BASE_URL}/v1/models/available", headers=headers)
    return response


if __name__ == "__main__":
    result = get_models()
    print(result)

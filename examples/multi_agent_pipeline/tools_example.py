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
        "agents": [
            {
                "agent_name": "Market Analyst",
                "description": "Analyzes market trends",
                "system_prompt": "You are a financial analyst expert.",
                "model_name": "openai/gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
                "tools_dictionary": [
                    {
                        "type": "function",
                        "function": {
                            "name": "search_topic",
                            "description": "Conduct an in-depth search on a specified topic or subtopic, generating a comprehensive array of highly detailed search queries tailored to the input parameters.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "depth": {
                                        "type": "integer",
                                        "description": "Indicates the level of thoroughness for the search. Values range from 1 to 3, where 1 represents a superficial search and 3 signifies an exploration of the topic.",
                                    },
                                    "detailed_queries": {
                                        "type": "array",
                                        "description": "An array of highly specific search queries that are generated based on the input query and the specified depth. Each query should be designed to elicit detailed and relevant information from various sources.",
                                        "items": {
                                            "type": "string",
                                            "description": "Each item in this array should represent a unique search query that targets a specific aspect of the main topic, ensuring a comprehensive exploration of the subject matter.",
                                        },
                                    },
                                },
                                "required": ["depth", "detailed_queries"],
                            },
                        },
                    },
                ],
            },
            {
                "agent_name": "Economic Forecaster",
                "description": "Predicts economic trends",
                "system_prompt": "You are an expert in economic forecasting.",
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
                "tools_dictionary": [
                    {
                        "type": "function",
                        "function": {
                            "name": "search_topic",
                            "description": "Conduct an in-depth search on a specified topic or subtopic, generating a comprehensive array of highly detailed search queries tailored to the input parameters.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "depth": {
                                        "type": "integer",
                                        "description": "Indicates the level of thoroughness for the search. Values range from 1 to 3, where 1 represents a superficial search and 3 signifies an exploration of the topic.",
                                    },
                                    "detailed_queries": {
                                        "type": "array",
                                        "description": "An array of highly specific search queries that are generated based on the input query and the specified depth. Each query should be designed to elicit detailed and relevant information from various sources.",
                                        "items": {
                                            "type": "string",
                                            "description": "Each item in this array should represent a unique search query that targets a specific aspect of the main topic, ensuring a comprehensive exploration of the subject matter.",
                                        },
                                    },
                                },
                                "required": ["depth", "detailed_queries"],
                            },
                        },
                    },
                ],
            },
        ],
        "max_loops": 1,
        "swarm_type": "ConcurrentWorkflow",
        "task": "What are the best etfs and index funds for ai and tech?",
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

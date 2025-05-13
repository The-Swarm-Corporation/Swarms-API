# tools - search, code executor, create api

import os
import requests
from dotenv import load_dotenv
import json


load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
# BASE_URL = "https://swarms-api-285321057562.us-east1.run.app"
BASE_URL = "https://api.swarms.world"

headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def run_health_check():
    response = requests.get(f"{BASE_URL}/health", headers=headers)
    return response.json()


def run_single_swarm():
    payload = {
        "name": "ICD-10 Diagnosis Swarm",
        "description": "Swarm for analyzing lab report data to provide ICD-10 diagnoses.",
        "agents": [
            {
                "agent_name": "Lab Data Analyzer",
                "description": "Analyzes lab report data to extract relevant medical information.",
                "system_prompt": "You are a medical data analyst specializing in interpreting lab results for diagnosis.",
                "model_name": "anthropic/claude-3-5-sonnet-latest",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "ICD-10 Code Specialist",
                "description": "Maps lab results to appropriate ICD-10 codes based on clinical guidelines.",
                "system_prompt": "You are an expert in ICD-10 coding and can provide accurate codes based on lab results.",
                "model_name": "claude-3-7-sonnet-latest",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Clinical Decision Support Agent",
                "description": "Provides clinical recommendations based on lab results and ICD-10 codes.",
                "system_prompt": "You are a clinical decision support agent that offers recommendations based on lab data and diagnoses.",
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
        ],
        "max_loops": 1,
        "swarm_type": "SequentialWorkflow",
        "task": "Analyze the following lab report data and provide ICD-10 diagnoses: Patient: 45-year-old White Male, Location: New York, NY, Lab Results: - egfr - 59 ml / min / 1.73 - non african-american",
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


if __name__ == "__main__":
    result = run_single_swarm()
    print("Swarm Result:")
    print(result)

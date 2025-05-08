import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "http://localhost:8080"

# Note: Remove Content-Type header here so that requests auto-sets the multipart boundary.
headers = {"x-api-key": API_KEY}


def run_single_swarm_with_audio():
    # Build the payload for all text fields.
    payload = {
        "name": "Financial Analysis Swarm",
        "description": "Market analysis swarm",
        "agents": json.dumps(
            [
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
                },
            ]
        ),
        "max_loops": "1",
        "swarm_type": "SequentialWorkflow",
        "task": "What are the best etfs and index funds for ai and tech?",
        "output_type": "dict",
    }

    # Path to your recorded audio file (should be one of the supported types, e.g., WAV).
    audio_file_path = "output.wav"

    # Open the audio file in binary mode.
    with open(audio_file_path, "rb") as audio_file:
        files = {
            "audio_file": (os.path.basename(audio_file_path), audio_file, "audio/wav")
        }

        response = requests.post(
            f"{BASE_URL}/v1/swarm/completions",
            headers=headers,
            data=payload,
            files=files,
        )

    print("Status Code:", response.status_code)
    try:
        output = response.json()
        print("Response:", json.dumps(output, indent=4))
    except Exception as e:
        print("Failed to parse JSON response:", e)
        print(response.text)


if __name__ == "__main__":
    run_single_swarm_with_audio()

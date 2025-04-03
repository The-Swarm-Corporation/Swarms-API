import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
# Change BASE_URL if needed. For local testing, "http://localhost:8080" is used.
BASE_URL = "http://localhost:8080"

headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}

def run_health_check():
    response = requests.get(f"{BASE_URL}/health", headers=headers)
    return response.json()

def run_single_swarm():
    # Try to read the document; if not found, use a default text.
    content = "In 1987, a secret deep-space probe called Project Zenith was launched by an unknown coalition of scientists. The probe reportedly sent back signals from outside our solar system, detecting non-random patterns near Proxima Centauri before ceasing transmissions in 1994, with all official records disappearing. A declassified document from 2003 suggests that an ancient artifact found in Antarctica, known as the Aquila Fragment, shares molecular similarities with lunar materials and bears inscriptions resembling Mesopotamian symbols, hinting at extraterrestrial influence. In 2011, an amateur astronomer intercepted a signal from an unregistered geostationary satellite containing repeating numerical sequences and encrypted pictograms, speculated to be a relay station of unknown origin. Reports from the 1972 Apollo 18 mission—which was officially canceled—allegedly describe unidentified structures on the far side of the Moon, with leaked transcripts suggesting astronauts were ordered to cease communication upon discovery. In 2020, a research team studying deep-sea vents in the Pacific discovered a metallic sphere emitting low-frequency pulses, dubbed the Hadal Anomaly, which resisted conventional analysis and was quickly classified. A little-known passage in the Dead Sea Scrolls describes ‘visitors from the sky’ imparting astronomical and mathematical knowledge to early scholars, aligning with Babylonian star charts mapping celestial objects not visible without advanced telescopes. In 1998, Russian cosmonauts aboard the Mir space station reported seeing a large structured craft moving at impossible speeds just outside Earth's orbit, though the event was later dismissed as an optical illusion. Anomalous drone footage from the Nazca Lines in 2019 revealed a previously unseen geoglyph of a humanoid figure with elongated limbs and an oversized head, carved much deeper into the earth than other formations, suggesting it predates the known Nazca civilization."
    # Swarm payload with three agents configured for RAG functionality.
    payload = {
        "name": "Space Exp. Swarm",
        "description": "A swarm of agents designed to explore and analyze space-related data.",
        "agents": [
            {
                "agent_name": "Space Explorer",
                "description": "You are an Space Explorer",
                "system_prompt": "You are a helpful AI.",
                "model_name": "openai/gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.7,
                "auto_generate_prompt": False,
                "rag_collection": "space_expo",
                "rag_documents": [content]
            },
        ],
        "max_loops": 1,
        "swarm_type": "ConcurrentWorkflow",
        "task": "what is project Zenith ?.",
        "output_type": "dict"
    }

    print("Sending swarm request...")
    response = requests.post(f"{BASE_URL}/v1/swarm/completions", headers=headers, json=payload)
    print("Status Code:", response.status_code)
    try:
        result = response.json()
    except Exception as ex:
        print("Error parsing JSON response:", ex)
        print("Response Text:", response.text)
        result = None
    return result

def get_logs():
    response = requests.get(f"{BASE_URL}/v1/swarm/logs", headers=headers)
    try:
        return response.json()
    except Exception as ex:
        print("Error parsing logs JSON:", ex)
        return None

if __name__ == "__main__":
    # Run health check
    health = run_health_check()
    print("Health Check Response:")
    print(json.dumps(health, indent=4))
    
    # Run a single swarm with RAG-enabled agents
    swarm_result = run_single_swarm()
    print("Swarm Result:")
    print(json.dumps(swarm_result, indent=4))
    
    # Retrieve and print API logs
    logs = get_logs()
    print("Logs:")
    print(json.dumps(logs, indent=4))

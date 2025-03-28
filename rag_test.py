import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8080"
API_KEY = os.getenv("SWARMS_API_KEY", "test-api-key")

headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

def log(msg):
    print("[TEST] " + msg)

def test_swarm_completion_with_rag_index_and_query():
    """Test indexing documents and querying in a single completions request"""
    url = f"{BASE_URL}/v1/swarms/completions"
    payload = {
        "name": "RAG Index and Query Test",
        "description": "Test indexing and querying in one request",
        "task": "Process RAG query",  # Added required task field
        "swarm_type": "ConcurrentWorkflow",
        "agents": [
            {
                "agent_name": "RAG Indexer Agent",
                "model_name": "gpt-4",
                "role": "worker",
                "max_loops": 1,
                "temperature": 0.3,
                "rag_collection": "qdrant_rag_collection",
                "rag_documents": [
                    "The author suggests taking small, consistent actions to build confidence.",
                    "Example: Write one paragraph per day instead of trying to write a whole book at once.",
                    "Focus on progress, not perfection, is the key message."
                ],
                "rag_query": "What does the author suggest for building confidence?"
            }
        ]
    }
    log("Running RAG indexing and query in one request...")
    response = requests.post(url, headers=headers, json=payload)
    log(f"Response Status Code: {response.status_code}")
    try:
        data = response.json()
        log("Response JSON:")
        log(json.dumps(data, indent=4))
        return response.status_code == 200 and "output" in data
    except Exception as e:
        log("Error decoding JSON: " + str(e))
        log("Response text: " + response.text)
        return False

def test_regular_swarm_completion():
    """Test regular swarm completion without RAG"""
    url = f"{BASE_URL}/v1/swarms/completions"
    payload = {
        "name": "Regular Swarm Test",
        "description": "Test regular swarm completion",
        "task": "Answer question about France",  # Added specific task
        "swarm_type": "ConcurrentWorkflow",
        "agents": [
            {
                "agent_name": "Test Agent 1",
                "model_name": "gpt-4",
                "role": "assistant",
                "max_loops": 1,
                "temperature": 0.7,
                "system_prompt": "You are a helpful assistant."
            }
        ]
    }
    log("Running regular swarm completion...")
    response = requests.post(url, headers=headers, json=payload)
    log(f"Response Status Code: {response.status_code}")
    try:
        data = response.json()
        log("Response JSON:")
        log(json.dumps(data, indent=4))
        return response.status_code == 200 and "output" in data
    except Exception as e:
        log("Error decoding JSON: " + str(e))
        log("Response text: " + response.text)
        return False

def test_batch_completions():
    """Test batch completions with multiple swarm specs"""
    url = f"{BASE_URL}/v1/swarm/batch/completions"
    payload = [
        {
            "name": "Batch Test 1",
            "task": "Perform math calculation",
            "swarm_type": "ConcurrentWorkflow",
            "agents": [{
                "agent_name": "Math Agent", 
                "model_name": "gpt-4",
                "role": "math_agent",
                "max_loops": 1,
                "temperature": 0.5
            }]
        },
        {
            "name": "Batch Test 2",
            "task": "Answer geography question",
            "swarm_type": "ConcurrentWorkflow",
            "agents": [{
                "agent_name": "Geography Agent", 
                "model_name": "gpt-4",
                "role": "geo_agent",
                "max_loops": 1,
                "temperature": 0.5
            }]
        }
    ]
    log("Running batch completions...")
    response = requests.post(url, headers=headers, json=payload)
    log(f"Response Status Code: {response.status_code}")
    try:
        data = response.json()
        log("Response JSON:")
        log(json.dumps(data, indent=4))
        return response.status_code == 200 and len(data) == 2
    except Exception as e:
        log("Error decoding JSON: " + str(e))
        log("Response text: " + response.text)
        return False

def main():
    log("Starting tests for Swarm API with integrated RAG functionality")
    
    # Run tests and track results
    test_results = {
        "rag_index_and_query": test_swarm_completion_with_rag_index_and_query(),
        "regular_completion": test_regular_swarm_completion(),
        "batch_completions": test_batch_completions()
    }
    
    # Print summary
    log("\nTest Results Summary:")
    for test_name, result in test_results.items():
        status = "PASSED" if result else "FAILED"
        log(f"{test_name}: {status}")
    
    # Calculate success rate
    passed_tests = sum(test_results.values())
    total_tests = len(test_results)
    success_rate = (passed_tests / total_tests) * 100
    log(f"\nOverall Success Rate: {success_rate:.2f}% ({passed_tests}/{total_tests} tests passed)")

if __name__ == "__main__":
    main()
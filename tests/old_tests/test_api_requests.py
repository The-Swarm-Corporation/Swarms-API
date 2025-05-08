import os
import time
import requests
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8080")
API_KEY = os.getenv("SWARMS_API_KEY")

HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def test_endpoint(
    endpoint: str, method: str = "GET", data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Generic test function for API endpoints
    """
    url = f"{API_BASE_URL}{endpoint}"

    try:
        if method == "GET":
            response = requests.get(url, headers=HEADERS)
        elif method == "POST":
            response = requests.post(url, headers=HEADERS, json=data)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        print(f"\n=== Testing {method} {endpoint} ===")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")

        return {
            "success": 200 <= response.status_code < 300,
            "status_code": response.status_code,
            "response": response.json(),
        }
    except Exception as e:
        print(f"Error testing {endpoint}: {str(e)}")
        return {"success": False, "error": str(e)}


def run_all_tests():
    """
    Run all API tests and report results
    """
    test_results = []
    total_tests = 0
    passed_tests = 0

    print("\n🚀 Starting API Test Suite...")
    start_time = time.time()

    # Test 1: Health Check
    result = test_endpoint("/health")
    total_tests += 1
    if result["success"] and result["response"].get("status") == "ok":
        passed_tests += 1
        test_results.append(("Health Check", "✅ PASSED"))
    else:
        test_results.append(("Health Check", "❌ FAILED"))

    # Test 2: Root Endpoint
    result = test_endpoint("/")
    total_tests += 1
    if result["success"]:
        passed_tests += 1
        test_results.append(("Root Endpoint", "✅ PASSED"))
    else:
        test_results.append(("Root Endpoint", "❌ FAILED"))

    # Test 3: Simple Swarm Completion
    simple_swarm = {
        "name": "test_swarm",
        "description": "A test swarm",
        "agents": [
            {
                "agent_name": "test_agent",
                "description": "A test agent",
                "system_prompt": "You are a helpful assistant",
                "model_name": "gpt-4",
                "temperature": 0.7,
                "max_loops": 1,
            }
        ],
        "task": "Say hello world",
        "max_loops": 1,
        "return_history": True,
    }

    result = test_endpoint("/v1/swarm/completions", "POST", simple_swarm)
    total_tests += 1
    if result["success"]:
        passed_tests += 1
        test_results.append(("Simple Swarm Completion", "✅ PASSED"))
    else:
        test_results.append(("Simple Swarm Completion", "❌ FAILED"))

    # Test 4: Batch Swarm Completion
    batch_swarms = [
        simple_swarm,
        simple_swarm,
    ]  # Using the same swarm twice for testing
    result = test_endpoint("/v1/swarm/batch/completions", "POST", batch_swarms)
    total_tests += 1
    if result["success"]:
        passed_tests += 1
        test_results.append(("Batch Swarm Completion", "✅ PASSED"))
    else:
        test_results.append(("Batch Swarm Completion", "❌ FAILED"))

    # Test 5: Get Logs
    result = test_endpoint("/v1/swarm/logs")
    total_tests += 1
    if result["success"]:
        passed_tests += 1
        test_results.append(("Get Logs", "✅ PASSED"))
    else:
        test_results.append(("Get Logs", "❌ FAILED"))

    # Print Test Results
    execution_time = time.time() - start_time
    print("\n=== Test Results ===")
    for test_name, result in test_results:
        print(f"{test_name}: {result}")

    print(f"\nTests Completed in {execution_time:.2f} seconds")
    print(
        f"Passed: {passed_tests}/{total_tests} ({(passed_tests/total_tests)*100:.1f}%)"
    )

    if passed_tests == total_tests:
        print("\n✨ All tests passed successfully! ✨")
    else:
        print(f"\n⚠️  {total_tests - passed_tests} tests failed!")


if __name__ == "__main__":
    run_all_tests()

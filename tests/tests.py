import requests
import json
import time
from datetime import datetime
from loguru import logger
import os
from typing import Any
import traceback
from dotenv import load_dotenv


load_dotenv()

# Constants
BASE_URL = "https://swarms-api-285321057562.us-east1.run.app"
# BASE_URL = "https://api.swarms.world"

# You should set your API key as an environment variable
API_KEY = os.environ.get("SWARMS_API_KEY")


class SwarmAPITest:
    """
    Test suite for Swarms API endpoints.

    This class contains test methods for all endpoints in the Swarms API,
    including health checks, swarm creation, batch processing, scheduling,
    and model information.
    """

    def __init__(self, base_url: str, api_key: str):
        """
        Initialize the test suite with base URL and API key.

        Args:
            base_url: The base URL of the Swarms API
            api_key: Your Swarms API key for authentication
        """
        self.base_url = base_url
        self.api_key = api_key
        self.headers = {"X-API-Key": self.api_key}
        self.test_results = {
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "total": 0,
            "details": [],
        }

    def _log_test(
        self, endpoint: str, status: str, response_data: Any = None, error: str = None
    ):
        """
        Log test results and update statistics.

        Args:
            endpoint: The API endpoint being tested
            status: Test status (passed, failed, skipped)
            response_data: API response data if available
            error: Error message if the test failed
        """
        result = {
            "endpoint": endpoint,
            "status": status,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        if response_data:
            result["response"] = response_data

        if error:
            result["error"] = error

        self.test_results["total"] += 1
        self.test_results[status] += 1
        self.test_results["details"].append(result)

        if status == "passed":
            logger.success(f"✅ Test passed: {endpoint}")
        elif status == "failed":
            logger.error(f"❌ Test failed: {endpoint} - {error}")
        else:
            logger.warning(f"⚠️ Test skipped: {endpoint}")

    def test_root_endpoint(self):
        """Test the root endpoint of the API."""
        endpoint = "/"

        try:
            logger.info(f"Testing {endpoint} endpoint")
            response = requests.get(f"{self.base_url}{endpoint}")

            if response.status_code == 200:
                self._log_test(endpoint, "passed", response.json())
                return True
            else:
                self._log_test(
                    endpoint,
                    "failed",
                    response.json() if response.text else None,
                    f"Unexpected status code: {response.status_code}",
                )
                return False
        except Exception as e:
            self._log_test(endpoint, "failed", None, str(e))
            return False

    def test_health_endpoint(self):
        """Test the health check endpoint."""
        endpoint = "/health"

        try:
            logger.info(f"Testing {endpoint} endpoint")
            response = requests.get(f"{self.base_url}{endpoint}")

            if response.status_code == 200 and response.json().get("status") == "ok":
                self._log_test(endpoint, "passed", response.json())
                return True
            else:
                self._log_test(
                    endpoint,
                    "failed",
                    response.json() if response.text else None,
                    f"Unexpected status code: {response.status_code} or response: {response.text}",
                )
                return False
        except Exception as e:
            self._log_test(endpoint, "failed", None, str(e))
            return False

    def test_available_swarms(self):
        """Test getting available swarm types."""
        endpoint = "/v1/swarms/available"

        try:
            logger.info(f"Testing {endpoint} endpoint")
            response = requests.get(f"{self.base_url}{endpoint}", headers=self.headers)

            print(f"Response code: {response.status_code}")
            print(response.json())

            if response.status_code == 200:
                self._log_test(endpoint, "passed", response.json())
                return True
            else:
                self._log_test(
                    endpoint,
                    "failed",
                    response.json() if response.text else None,
                    f"Unexpected status code: {response.status_code}",
                )
                return False
        except Exception as e:
            self._log_test(endpoint, "failed", None, str(e))
            return False

    def test_available_models(self):
        """Test getting available model types."""
        endpoint = "/v1/models/available"

        try:
            logger.info(f"Testing {endpoint} endpoint")
            response = requests.get(f"{self.base_url}{endpoint}", headers=self.headers)

            if response.status_code == 200:
                self._log_test(endpoint, "passed", response.json())
                return True
            else:
                self._log_test(
                    endpoint,
                    "failed",
                    response.json() if response.text else None,
                    f"Unexpected status code: {response.status_code}",
                )
                return False
        except Exception as e:
            self._log_test(endpoint, "failed", None, str(e))
            return False

    def test_swarm_completion(self):
        """Test running a single swarm task."""
        endpoint = "/v1/swarm/completions"

        try:
            logger.info(f"Testing {endpoint} endpoint")

            # Basic swarm payload with a simple task
            payload = {
                "name": f"test-swarm-{int(time.time())}",
                "description": "Test swarm for API validation",
                "swarm_type": "SequentialWorkflow",
                "task": "Write a short poem about AI",
                "agents": [
                    {
                        "agent_name": "poet",
                        "description": "A creative poet agent",
                        "model_name": "gpt-4o-mini",
                        "system_prompt": "You are a talented poet who specializes in short, evocative poems.",
                        "temperature": 0.7,
                        "max_loops": 1,
                        "role": "worker",
                    },
                    {
                        "agent_name": "editor",
                        "description": "An editor who refines poems",
                        "model_name": "gpt-4o-mini",
                        "system_prompt": "You are an editor who helps refine poems to make them more impactful.",
                        "temperature": 0.4,
                        "max_loops": 1,
                        "role": "worker",
                    },
                ],
                "max_loops": 1,
                "return_history": True,
            }

            response = requests.post(
                f"{self.base_url}{endpoint}", headers=self.headers, json=payload
            )

            if response.status_code == 200:
                logger.debug(f"Swarm completion response: {response.json()}")
                self._log_test(endpoint, "passed", response.json())
                return True
            else:
                self._log_test(
                    endpoint,
                    "failed",
                    response.json() if response.text else None,
                    f"Unexpected status code: {response.status_code}",
                )
                return False
        except Exception as e:
            logger.error(f"Exception in test_swarm_completion: {str(e)}")
            logger.debug(traceback.format_exc())
            self._log_test(endpoint, "failed", None, str(e))
            return False

    # def test_auto_generate_agents(self):
    #     """Test auto-generating agents for a task."""
    #     endpoint = "/v1/agents/auto-generate"

    #     try:
    #         logger.info(f"Testing {endpoint} endpoint")

    #         payload = {"task": "Create a data analysis plan for customer retention"}

    #         response = requests.post(
    #             f"{self.base_url}{endpoint}", headers=self.headers, json=payload
    #         )

    #         if response.status_code == 200:
    #             self._log_test(
    #                 endpoint,
    #                 "passed",
    #                 {"message": "Successfully auto-generated agents"},
    #             )
    #             return True
    #         else:
    #             self._log_test(
    #                 endpoint,
    #                 "failed",
    #                 response.json() if response.text else None,
    #                 f"Unexpected status code: {response.status_code}",
    #             )
    #             return False
    #     except Exception as e:
    #         self._log_test(endpoint, "failed", None, str(e))
    #         return False

    def test_batch_completions(self):
        """Test running multiple swarms in batch mode."""
        endpoint = "/v1/swarm/batch/completions"

        try:
            logger.info(f"Testing {endpoint} endpoint")

            # Create a batch of two simple swarms
            batch_payload = [
                {
                    "name": f"batch-test-1-{int(time.time())}",
                    "description": "First batch test swarm",
                    "swarm_type": "SequentialWorkflow",
                    "task": "List 3 benefits of AI",
                    "agents": [
                        {
                            "agent_name": "researcher",
                            "description": "An agent that researches AI benefits",
                            "model_name": "gpt-4o-mini",
                            "system_prompt": "You are a researcher who specializes in AI benefits.",
                            "temperature": 0.5,
                            "max_loops": 1,
                            "role": "worker",
                        }
                    ],
                    "max_loops": 1,
                },
                {
                    "name": f"batch-test-2-{int(time.time())}",
                    "description": "Second batch test swarm",
                    "swarm_type": "SequentialWorkflow",
                    "task": "List 3 challenges of AI",
                    "agents": [
                        {
                            "agent_name": "analyst",
                            "description": "An agent that analyzes AI challenges",
                            "model_name": "gpt-4o-mini",
                            "system_prompt": "You are an analyst who specializes in identifying AI challenges.",
                            "temperature": 0.5,
                            "max_loops": 1,
                            "role": "worker",
                        }
                    ],
                    "max_loops": 1,
                },
            ]

            response = requests.post(
                f"{self.base_url}{endpoint}", headers=self.headers, json=batch_payload
            )

            if response.status_code == 200:
                self._log_test(
                    endpoint,
                    "passed",
                    {"message": "Successfully processed batch request"},
                )
                return True
            else:
                self._log_test(
                    endpoint,
                    "failed",
                    response.json() if response.text else None,
                    f"Unexpected status code: {response.status_code}",
                )
                return False
        except Exception as e:
            self._log_test(endpoint, "failed", None, str(e))
            return False

    # def test_schedule_swarm(self):
    #     """Test scheduling a swarm to run at a future time."""
    #     endpoint = "/v1/swarm/schedule"

    #     try:
    #         logger.info(f"Testing {endpoint} endpoint")

    #         # Schedule a swarm 10 minutes in the future
    #         future_time = datetime.utcnow() + timedelta(minutes=10)

    #         payload = {
    #             "name": f"scheduled-swarm-{int(time.time())}",
    #             "description": "Test scheduled swarm",
    #             "swarm_type": "SequentialWorkflow",
    #             "task": "List 5 trends in AI for the next year",
    #             "agents": [
    #                 {
    #                     "agent_name": "forecaster",
    #                     "description": "An agent that forecasts AI trends",
    #                     "model_name": "gpt-4o-mini",
    #                     "system_prompt": "You are an AI trend forecaster with expertise in technology trends.",
    #                     "temperature": 0.6,
    #                     "max_loops": 1,
    #                     "role": "worker",
    #                 }
    #             ],
    #             "max_loops": 1,
    #             "schedule": {
    #                 "scheduled_time": future_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    #                 "timezone": "UTC",
    #             },
    #         }

    #         response = requests.post(
    #             f"{self.base_url}{endpoint}", headers=self.headers, json=payload
    #         )

    #         if response.status_code == 200:
    #             # Store the job_id for cleanup later
    #             job_id = response.json().get("job_id")
    #             logger.info(f"Created scheduled job with ID: {job_id}")
    #             self._log_test(endpoint, "passed", response.json())

    #             # Also test getting scheduled jobs
    #             self.test_get_scheduled_jobs()

    #             # Clean up by cancelling the job
    #             if job_id:
    #                 self.test_cancel_scheduled_job(job_id)

    #             return True
    #         else:
    #             self._log_test(
    #                 endpoint,
    #                 "failed",
    #                 response.json() if response.text else None,
    #                 f"Unexpected status code: {response.status_code}",
    #             )
    #             return False
    #     except Exception as e:
    #         self._log_test(endpoint, "failed", None, str(e))
    #         return False

    def test_get_scheduled_jobs(self):
        """Test retrieving all scheduled jobs."""
        endpoint = "/v1/swarm/schedule"

        try:
            logger.info(f"Testing GET {endpoint} endpoint")

            response = requests.get(f"{self.base_url}{endpoint}", headers=self.headers)

            if response.status_code == 200:
                self._log_test(endpoint, "passed", response.json())
                return True
            else:
                self._log_test(
                    endpoint,
                    "failed",
                    response.json() if response.text else None,
                    f"Unexpected status code: {response.status_code}",
                )
                return False
        except Exception as e:
            self._log_test(endpoint, "failed", None, str(e))
            return False

    def test_cancel_scheduled_job(self, job_id: str):
        """
        Test cancelling a scheduled job.

        Args:
            job_id: ID of the scheduled job to cancel
        """
        endpoint = f"/v1/swarm/schedule/{job_id}"

        try:
            logger.info(f"Testing DELETE {endpoint} endpoint")

            response = requests.delete(
                f"{self.base_url}{endpoint}", headers=self.headers
            )

            if response.status_code == 200:
                self._log_test(endpoint, "passed", response.json())
                return True
            else:
                self._log_test(
                    endpoint,
                    "failed",
                    response.json() if response.text else None,
                    f"Unexpected status code: {response.status_code}",
                )
                return False
        except Exception as e:
            self._log_test(endpoint, "failed", None, str(e))
            return False

    def test_swarm_logs(self):
        """Test retrieving API request logs."""
        endpoint = "/v1/swarm/logs"

        try:
            logger.info(f"Testing {endpoint} endpoint")

            response = requests.get(f"{self.base_url}{endpoint}", headers=self.headers)

            if response.status_code == 200:
                self._log_test(
                    endpoint, "passed", {"message": "Successfully retrieved logs"}
                )
                return True
            else:
                self._log_test(
                    endpoint,
                    "failed",
                    response.json() if response.text else None,
                    f"Unexpected status code: {response.status_code}",
                )
                return False
        except Exception as e:
            self._log_test(endpoint, "failed", None, str(e))
            return False

    def run_all_tests(self):
        """
        Run all API endpoint tests and generate a final report.

        Returns:
            Dict containing test results and statistics
        """
        logger.info("Starting Swarms API test suite")

        # Basic endpoints
        self.test_root_endpoint()
        self.test_health_endpoint()

        # Information endpoints
        self.test_available_swarms()
        self.test_available_models()

        # Core functionality endpoints
        self.test_swarm_completion()
        # self.test_auto_generate_agents()
        self.test_batch_completions()

        # Scheduling endpoints
        # self.test_schedule_swarm()

        # Logs endpoint
        self.test_swarm_logs()

        # Generate and return final report
        return self.generate_report()

    def generate_report(self):
        """
        Generate a detailed test report.

        Returns:
            Dict containing test results, statistics and conclusion
        """
        report = {
            "test_run_info": {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "base_url": self.base_url,
                "total_tests": self.test_results["total"],
                "passed": self.test_results["passed"],
                "failed": self.test_results["failed"],
                "skipped": self.test_results["skipped"],
                "success_rate": round(
                    self.test_results["passed"]
                    / max(self.test_results["total"], 1)
                    * 100,
                    2,
                ),
            },
            "test_details": self.test_results["details"],
            "conclusion": (
                "All tests passed!"
                if self.test_results["failed"] == 0
                else f"{self.test_results['failed']} tests failed. See details above."
            ),
        }

        # Print summary to terminal
        logger.info("\n" + "=" * 50)
        logger.info("SWARMS API TEST REPORT")
        logger.info("=" * 50)
        logger.info(f"Total tests: {report['test_run_info']['total_tests']}")
        logger.info(f"Passed: {report['test_run_info']['passed']}")
        logger.info(f"Failed: {report['test_run_info']['failed']}")
        logger.info(f"Skipped: {report['test_run_info']['skipped']}")
        logger.info(f"Success rate: {report['test_run_info']['success_rate']}%")
        logger.info(f"Conclusion: {report['conclusion']}")
        logger.info("=" * 50)

        return report


def main():
    """Main function to run the Swarms API test suite."""
    try:
        # Check if API key is provided
        if API_KEY == "your-api-key-here":
            logger.warning(
                "⚠️ No API key provided! Set your SWARMS_API_KEY environment variable."
            )
            logger.warning("Some tests will fail without a valid API key.")

        # Create and run test suite
        test_suite = SwarmAPITest(BASE_URL, API_KEY)
        report = test_suite.run_all_tests()

        # Save report to file
        with open("swarms_api_test_report.json", "w") as f:
            json.dump(report, f, indent=4)

        logger.info("Test report saved to swarms_api_test_report.json")

        return report
    except Exception as e:
        logger.error(f"Error running test suite: {str(e)}")
        logger.debug(traceback.format_exc())
        return {"error": str(e)}


if __name__ == "__main__":
    main()

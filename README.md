# Swarms API 

Build, deploy, and orchestrate AI agents at scale with ease. Swarms API provides a comprehensive suite of endpoints for creating and managing multi-agent systems.

**Languages:** [English](README.md) | [中文](README.zh.md)


## Features

- **Swarms API**: A powerful REST API for managing and executing multi-agent systems with ease.
- **Flexible Model Support**: Utilize various AI models, including GPT-4o, Claude, Deepseek, and custom models tailored to your needs.
- **Diverse Swarm Architectures**: Choose from multiple swarm architectures such as Concurrent, Sequential, and Hybrid workflows to optimize task execution.
- **Dynamic Agent Configuration**: Easily configure agents with customizable parameters for different roles and tasks.
- **Supabase Integration**: Built-in database support for logging, API key management, and user authentication.
- **Real-time Monitoring**: Track swarm performance and execution metrics in real-time for better insights and adjustments.
- **Batch Processing**: Execute multiple swarm tasks simultaneously for enhanced efficiency and throughput.
- **Job Scheduling**: Schedule swarm executions for future times to automate recurring tasks.
- **Job Scheduling**: Schedule swarm executions for future times to automate recurring tasks.
- **Usage Tracking**: Monitor API usage and credit consumption.

## API Documentation & Resources

- **Documentation**: [Swarms API Docs](https://docs.swarms.world/en/latest/swarms_cloud/swarms_api/)
- **Pricing Information**: [API Pricing](https://docs.swarms.world/en/latest/swarms_cloud/api_pricing/)
- **API Keys**: [Get API Keys](https://swarms.world/platform/api-keys)

## API Endpoints

### Core Endpoints

| Endpoint | Method | Description | Parameters |
|----------|--------|-------------|------------|
| `/health` | GET | Check API health | None |
| `/v1/swarms/available` | GET | List available swarm types | None |

### Swarm Operation Endpoints

| Endpoint | Method | Description | Parameters |
|----------|--------|-------------|------------|
| `/v1/swarm/completions` | POST | Run a single swarm task | `SwarmSpec` object |
| `/v1/swarm/batch/completions` | POST | Run multiple swarm tasks | Array of `SwarmSpec` objects |
| `/v1/swarm/logs` | GET | Retrieve API request logs | None |

### Scheduling Endpoints

| Endpoint | Method | Description | Parameters |
|----------|--------|-------------|------------|
| `/v1/swarm/schedule` | POST | Schedule a swarm task | `SwarmSpec` with `schedule` object |
| `/v1/swarm/schedule` | GET | List all scheduled jobs | None |
| `/v1/swarm/schedule/{job_id}` | DELETE | Cancel a scheduled job | `job_id` |

## Request Parameters

### SwarmSpec Object

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | No | Name of the swarm |
| `description` | string | No | Description of the swarm's purpose |
| `agents` | array | Yes | Array of agent configurations |
| `max_loops` | integer | No | Maximum iteration loops (default: 1) |
| `swarm_type` | string | No | Type of workflow ("ConcurrentWorkflow", "SequentialWorkflow", etc.) |
| `rearrange_flow` | string | No | Instructions to rearrange workflow |
| `task` | string | Yes | The task to be performed |
| `img` | string | No | Optional image URL |
| `return_history` | boolean | No | Include conversation history (default: true) |
| `rules` | string | No | Guidelines for agent behavior |
| `schedule` | object | No | Scheduling details (for scheduled jobs) |

### AgentSpec Object

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_name` | string | Yes | Name of the agent |
| `description` | string | No | Agent's purpose description |
| `system_prompt` | string | No | System prompt for the agent |
| `model_name` | string | Yes | AI model to use (e.g., "gpt-4o", "claude-3-opus") |
| `auto_generate_prompt` | boolean | No | Generate prompts automatically |
| `max_tokens` | integer | No | Maximum tokens for responses (default: 8192) |
| `temperature` | float | No | Response randomness (default: 0.5) |
| `role` | string | No | Agent's role (default: "worker") |
| `max_loops` | integer | No | Maximum loops for this agent (default: 1) |

### ScheduleSpec Object

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scheduled_time` | datetime | Yes | When to execute the task (in UTC) |
| `timezone` | string | No | Timezone for scheduling (default: "UTC") |

## Swarm Types

- `AgentRearrange`
- `MixtureOfAgents`
- `SpreadSheetSwarm`
- `SequentialWorkflow`
- `ConcurrentWorkflow`
- `GroupChat`
- `MultiAgentRouter`
- `AutoSwarmBuilder`
- `HiearchicalSwarm`
- `auto`
- `MajorityVoting`

## Authentication

All API endpoints (except health check) require an API key passed in the `x-api-key` header:

```bash
curl -H "x-api-key: your_api_key" -H "Content-Type: application/json" -X POST https://api.swarms.world/v1/swarm/completions
```

## Example Usage

Here's a basic example of running a swarm with multiple agents:

```python
import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://api.swarms.world"

headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}

def run_single_swarm():
    payload = {
        "name": "Financial Analysis Swarm",
        "description": "Market analysis swarm",
        "agents": [
            {
                "agent_name": "Market Analyst",
                "description": "Analyzes market trends",
                "system_prompt": "You are a financial analyst expert.",
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5
            },
            {
                "agent_name": "Economic Forecaster",
                "description": "Predicts economic trends",
                "system_prompt": "You are an expert in economic forecasting.",
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.7
            },
            {
                "agent_name": "Data Scientist",
                "description": "Performs data analysis",
                "system_prompt": "You are a data science expert.",
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.3
            },
        ],
        "max_loops": 1,
        "swarm_type": "ConcurrentWorkflow",
        "task": "What are the best ETFs and index funds for AI and tech?",
        "return_history": True,
    }

    response = requests.post(
        f"{BASE_URL}/v1/swarm/completions",
        headers=headers,
        json=payload,
    )

    return json.dumps(response.json(), indent=4)

if __name__ == "__main__":
    result = run_single_swarm()
    print("Swarm Result:")
    print(result)
```

## Scheduling Example

```python
import datetime
import pytz
from datetime import timedelta

# Schedule a swarm to run in 1 hour
future_time = datetime.datetime.now(pytz.UTC) + timedelta(hours=1)

schedule_payload = {
    "name": "Daily Market Analysis",
    "agents": [
        {
            "agent_name": "Market Analyzer",
            "model_name": "gpt-4o",
            "system_prompt": "You analyze financial markets daily"
        }
    ],
    "swarm_type": "SequentialWorkflow",
    "task": "Provide a summary of today's market movements",
    "schedule": {
        "scheduled_time": future_time.isoformat(),
        "timezone": "America/New_York"
    }
}

response = requests.post(
    f"{BASE_URL}/v1/swarm/schedule",
    headers=headers,
    json=schedule_payload
)
```

## Credit Usage

API usage consumes credits based on:
1. Number of agents used
2. Input/output token count
3. Model selection
4. Time of day (discounts during off-peak hours)

For detailed pricing information, visit the [API Pricing](https://docs.swarms.world/en/latest/swarms_cloud/api_pricing/) page.

## Error Handling

Common HTTP status codes:
- `200`: Success
- `400`: Bad request (invalid parameters)
- `401`: Unauthorized (invalid or missing API key)
- `402`: Payment required (insufficient credits)
- `429`: Rate limit exceeded
- `500`: Internal server error

## Getting Support

For questions or support:
- Check the [documentation](https://docs.swarms.world/en/latest/swarms_cloud/swarms_api/)
- Pricing Docs: [Pricing Docs](https://docs.swarms.world/en/latest/swarms_cloud/api_pricing/)
- Contact kye@swarms.world

# Todo List for API Optimization and Feature Additions

[PRIORITY][SPEED]

## Performance Optimizations
- [ ] Implement connection pooling for Supabase client
- [z] Increase LRU cache sizes for API key verification functions
- [ ] Add caching for token counting operations
- [x] Implement batch logging for API requests
- [ ] Create asynchronous version of deduct_credits function
- [ ] Use ThreadPoolExecutor for parallel agent creation
- [ ] Optimize Uvicorn server settings (workers, loop, concurrency limits)
- [x] Disable debug mode in production environment
- [ ] Add uvloop for faster event loop processing
- [x] Implement request batching for database operations

## New Features
- [ ] Add health monitoring endpoint with detailed system stats
- [ ] Implement user quota management system
- [ ] Create API key rotation functionality
- [ ] Add support for agent templates/presets
- [ ] Implement webhook notifications for completed swarm tasks
- [ ] Add support for long-running swarm tasks with status updates
- [ ] Create a caching layer for frequently used swarm configurations
- [ ] Implement rate limiting based on user tiers
- [ ] Add support for custom tool integrations
- [ ] Create a job queue system for high-load scenarios

## Security Enhancements
- [ ] Implement API key scoping (read-only, write, admin)
- [ ] Add request signing for enhanced security
- [ ] Implement IP-based access controls
- [ ] Create audit logging for security-sensitive operations
- [ ] Add encryption for sensitive data in logs and database
- [ ] Implement automatic suspicious activity detection

## Monitoring & Observability
- [ ] Add detailed performance metrics collection
- [ ] Implement structured logging with correlation IDs
- [ ] Create dashboard for real-time API usage monitoring
- [ ] Add alerting for system issues and anomalies
- [ ] Implement distributed tracing for request flows
- [ ] Create periodic performance reports

## Developer Experience
- [x] Add comprehensive API documentation with examples
- [ ] Create SDK libraries for common programming languages
- [ ] Implement playground/testing environment
- [ ] Add request/response validation with detailed error messages
- [x] Create interactive API explorer -- cloud.swarms.ai
- [x] Implement versioned API endpoints

## Reliability Improvements
- [ ] Add circuit breaker pattern for external dependencies
- [ ] Implement graceful degradation for non-critical features
- [ ] Create automated backup and restore procedures
- [ ] Add retry logic for transient failures
- [ ] Implement fallback mechanisms for critical operations

## Multi-Modality Processing
- [ ] Implement speech-to-text conversion for audio input processing
- [ ] Add text-to-speech capabilities for voice response generation
- [ ] Create image analysis and processing pipeline for visual inputs
- [ ] Develop video processing capabilities for temporal visual data
- [ ] Implement document parsing and extraction for PDFs, DOCs, etc.
- [ ] Add OCR functionality for text extraction from images
- [ ] Create multi-modal agent capabilities (combining text, image, audio)
- [ ] Implement cross-modal reasoning between different data types
- [ ] Add support for generating images from text descriptions
- [ ] Develop capabilities for video summarization and analysis


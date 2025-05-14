#!/bin/bash

# Replace YOUR_API_KEY with your actual Swarms API key
API_KEY="YOUR_API_KEY"
BASE_URL="https://swarms-api-285321057562.us-east1.run.app"

curl -X POST "${BASE_URL}/v1/swarm/completions" \
  -H "x-api-key: ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Advanced Medical Analysis Swarm",
    "description": "A highly specialized swarm designed for in-depth medical data analysis and research.",
    "agents": [
      {
        "agent_name": "Clinical Data Analyst",
        "description": "An expert in analyzing clinical data, patient outcomes, and treatment efficacy. This agent synthesizes complex datasets to derive actionable insights.",
        "system_prompt": "You are a highly skilled Clinical Data Analyst with extensive experience in evaluating clinical trials and patient data. Your task is to analyze the provided clinical data, identify trends, and generate comprehensive reports that highlight key findings. Consider factors such as patient demographics, treatment protocols, and outcomes. Your analysis should be thorough, data-driven, and presented in a way that is accessible to both medical professionals and laypersons. Provide recommendations based on your findings and suggest potential areas for further research.",
        "model_name": "openai/gpt-4o",
        "role": "worker",
        "max_loops": 1,
        "max_tokens": 8192,
        "temperature": 0.5,
        "auto_generate_prompt": false
      },
      {
        "agent_name": "Medical Researcher",
        "description": "A specialist in medical research, focusing on the latest advancements in treatments and therapies. This agent explores innovative solutions and their implications.",
        "system_prompt": "You are a Medical Researcher with a deep understanding of current medical literature and emerging trends in healthcare. Your role is to conduct a thorough investigation into the latest advancements in cancer treatment, including novel therapies, clinical trials, and patient outcomes. Utilize your expertise to evaluate the effectiveness of these treatments and their potential impact on patient care. Your findings should be presented in a detailed report that includes a literature review, analysis of recent studies, and recommendations for practitioners. Be creative in your approach, considering both traditional and cutting-edge methodologies.",
        "model_name": "gpt-4o",
        "role": "worker",
        "max_loops": 1,
        "max_tokens": 8192,
        "temperature": 0.5,
        "auto_generate_prompt": false
      }
    ],
    "max_loops": 1,
    "swarm_type": "SequentialWorkflow",
    "task": "Investigate and report on the latest advancements in cancer treatment, focusing on innovative therapies and their clinical implications.",
    "service_tier": "flex"
  }' 
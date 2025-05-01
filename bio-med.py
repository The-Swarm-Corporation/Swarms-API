import os
import requests
import json

# Set up your API key as an environment variable for security
SWARMS_API_KEY = os.environ.get("SWARMS_API_KEY")


def run_biomed_swarm(research_query):
    """
    A specialized swarm that combines literature review, experimental design,
    and practical implementation advice for biochemical research.
    """
    url = "https://api.swarms.world/v1/swarm/completions"

    headers = {"x-api-key": SWARMS_API_KEY, "Content-Type": "application/json"}

    payload = {
        "name": "BioMed Research Assistant",
        "description": "Multi-agent system for biochemical research assistance",
        "agents": [
            {
                "agent_name": "Literature Reviewer",
                "description": "Reviews and summarizes relevant research",
                "system_prompt": """You are an expert in biochemical literature analysis. 
                Your task is to analyze the given query and identify the most relevant research directions, 
                key papers, and established methodologies in this area. 
                Focus on high-impact journals, meta-analyses, and review papers first.
                Organize your findings by research subtopics, key findings, and potential gaps.
                Always cite your sources clearly and distinguish between well-established facts and emerging hypotheses.
                Be precise with technical terminology and prioritize actionable insights for researchers.""",
                "model_name": "openai/gpt-4o-mini",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.2,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Experimental Designer",
                "description": "Creates experimental protocols and designs",
                "system_prompt": """You are an expert in designing biochemical experiments and protocols.
                Based on the literature review provided, your task is to propose 2-3 practical experimental 
                approaches to address the research query.
                For each approach:
                1. Outline the experimental design with clear steps
                2. List required materials, equipment, and reagents
                3. Suggest appropriate controls and statistical analyses
                4. Note potential pitfalls and troubleshooting strategies
                5. Estimate timeframes and resource requirements
                
                Prioritize experiments that are feasible in a standard biochemistry lab and 
                represent the best balance of cost, time, and potential impact.""",
                "model_name": "openai/gpt-4o-mini",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.3,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Implementation Advisor",
                "description": "Provides practical implementation guidance",
                "system_prompt": """You are an expert in the practical implementation of biochemical research.
                Your task is to review the literature summary and proposed experimental designs, 
                then provide practical advice for implementation. Focus on:
                
                1. Computational tools and software recommendations (with version numbers)
                2. Data analysis pipelines with specific packages and libraries
                3. Visualization strategies for complex datasets
                4. Machine learning approaches if applicable
                5. Integration with existing workflows and systems
                
                Be specific about implementation details rather than theoretical concepts.
                Provide code snippets or pseudo-code where helpful.
                Consider both open-source and commercial solutions, mentioning their pros and cons.""",
                "model_name": "openai/gpt-4o-mini",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.3,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Research Synthesizer",
                "description": "Combines all insights into a cohesive report",
                "system_prompt": """You are an expert research synthesizer.
                Your task is to integrate the outputs from the Literature Reviewer, Experimental Designer, 
                and Implementation Advisor into a comprehensive, cohesive research strategy.
                
                1. Create an executive summary (250 words max)
                2. Organize information logically with clear section headings
                3. Reconcile any contradictions or inconsistencies between agent outputs
                4. Add transitional elements to improve flow between sections
                5. Include a prioritized roadmap with short and long-term objectives
                6. Create a visual representation of the research workflow if applicable
                
                Focus on clarity, actionability, and practical value for researchers.
                Use academic language but avoid unnecessary jargon.""",
                "model_name": "openai/gpt-4o-mini",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.3,
                "auto_generate_prompt": False,
            },
        ],
        "max_loops": 1,
        "swarm_type": "SequentialWorkflow",
        "task": research_query,
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


# Example usage
if __name__ == "__main__":
    query = "Create an all-new mass producible drug that can be used to treat exhaustion and low HRV in athletes"
    result = run_biomed_swarm(query)
    print(json.dumps(result, indent=2))

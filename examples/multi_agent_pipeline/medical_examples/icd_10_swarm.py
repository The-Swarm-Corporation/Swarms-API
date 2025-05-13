import json
import os

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv("SWARMS_API_KEY")
# BASE_URL = "https://api.swarms.world"
BASE_URL = "https://swarms-api-285321057562.us-east1.run.app"

# Standard headers for all requests
headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def run_swarm(swarm_config):
    """Execute a swarm with the provided configuration."""
    response = requests.post(
        f"{BASE_URL}/v1/swarm/completions", headers=headers, json=swarm_config
    )
    return response.json()


def create_icd10_coding_swarm(clinical_documentation):
    """
    Create a swarm for ICD-10 coding assistance.

    Args:
        clinical_documentation (str): Clinical notes, discharge summary, or other medical documentation

    Returns:
        dict: The swarm execution result containing ICD-10 codes with justifications.
    """

    # Define specialized prompts for medical coding
    CODE_EXTRACTOR_PROMPT = """
    You are a precise ICD-10 code extractor. Your sole purpose is to identify and list ICD-10 codes from clinical documentation.

    Your tasks:
    1. Extract ONLY the ICD-10 codes from the clinical documentation
    2. List them in order of importance (principal diagnosis first)
    3. Do not include any explanations or justifications
    4. Format the output as a clean list of codes

    Rules:
    - Only include codes that are explicitly supported by the documentation
    - Use the most specific code available
    - Follow proper code sequencing guidelines
    - Do not infer or assume conditions not stated
    - Format output as a simple list of codes, one per line
    """

    CODE_EXPLAINER_PROMPT = """
    You are an expert ICD-10 code explainer. Your role is to provide clear, concise explanations for each ICD-10 code.

    For each code provided, explain:
    1. What the code represents
    2. Why this specific code was chosen
    3. The key documentation elements that support this code
    4. Any important coding guidelines that apply

    Format your response as:
    Code: [ICD-10 code]
    Description: [What the code means]
    Justification: [Why this code was chosen]
    Supporting Documentation: [Key clinical elements]
    Guidelines: [Relevant coding rules]

    Keep explanations clear and focused on the specific code.
    """

    CODE_VALIDATOR_PROMPT = """
    You are a thorough ICD-10 code validator. Your role is to verify the accuracy and completeness of the code assignments.

    For each code and its explanation, verify:
    1. Code accuracy and specificity
    2. Documentation support
    3. Proper sequencing
    4. Compliance with coding guidelines
    5. Missing required additional codes

    Provide validation feedback in this format:
    Code: [ICD-10 code]
    Validation Status: [Valid/Needs Review]
    Issues Found: [List any concerns]
    Recommendations: [Suggestions for improvement]
    Documentation Gaps: [Missing elements]

    Focus on identifying potential issues and opportunities for improvement.
    """

    # Configure the ICD-10 coding swarm
    swarm_config = {
        "name": "ICD-10 Coding Assistant",
        "description": "A specialized swarm for accurate ICD-10 coding with explanation and validation",
        "agents": [
            {
                "agent_name": "Code Extractor",
                "description": "Extracts ICD-10 codes from clinical documentation",
                "system_prompt": CODE_EXTRACTOR_PROMPT,
                "model_name": "groq/llama3-70b-8192",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.3,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Code Explainer",
                "description": "Explains the rationale for each ICD-10 code",
                "system_prompt": CODE_EXPLAINER_PROMPT,
                "model_name": "groq/llama3-70b-8192",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Code Validator",
                "description": "Validates code assignments and explanations",
                "system_prompt": CODE_VALIDATOR_PROMPT,
                "model_name": "groq/deepseek-r1-distill-llama-70b",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.3,
                "auto_generate_prompt": False,
            },
        ],
        "max_loops": 1,
        "swarm_type": "ConcurrentWorkflow",
        "task": f"""
        Analyze the following clinical documentation and provide:
        1. A list of appropriate ICD-10-CM codes
        2. Detailed explanation for each code
        3. Validation of the code assignments

        Clinical Documentation:
        {clinical_documentation}
        """,
    }

    # Execute the swarm
    result = run_swarm(swarm_config)
    return result


def run_example_icd10_coding():
    """Run an example ICD-10 coding case."""

    # Example clinical documentation
    clinical_documentation = """
    DISCHARGE SUMMARY

    Patient: John Smith
    MRN: 12345678
    DOB: 01/15/1962
    Admission Date: 06/10/2023
    Discharge Date: 06/15/2023

    FINAL DIAGNOSES:
    1. Acute exacerbation of chronic systolic congestive heart failure
    2. Non-ST elevation myocardial infarction
    3. Type 2 diabetes mellitus with diabetic nephropathy, estimated GFR 42
    4. Hypertension
    5. Hyperlipidemia

    HISTORY OF PRESENT ILLNESS:
    The patient is a 61-year-old male with a history of congestive heart failure (EF 35% on prior echo 3 months ago) who presented to the emergency department with a 3-day history of worsening shortness of breath, orthopnea, and lower extremity edema. The patient reported chest pressure while walking to the bathroom. Initial troponin was elevated at 0.15 ng/mL, with subsequent rise to 0.25 ng/mL, consistent with NSTEMI. BNP was significantly elevated at 1,250 pg/mL.

    HOSPITAL COURSE:
    The patient was admitted to the cardiac care unit. He was treated with IV furosemide with good diuretic response, losing 3.5 liters of fluid during hospitalization. Cardiology was consulted and performed a left heart catheterization, which revealed 70% stenosis in the mid-LAD with PCI and drug-eluting stent placement. The patient's symptoms improved significantly with diuresis and coronary intervention.

    His diabetes was managed with insulin during the hospitalization, with blood glucose ranging from 130-210 mg/dL. Nephrology was consulted regarding his diabetic nephropathy and recommended adjustment of medications appropriate for his renal function.

    PROCEDURES:
    1. Left heart catheterization with percutaneous coronary intervention and drug-eluting stent placement to mid-LAD (06/12/2023)

    DISCHARGE MEDICATIONS:
    1. Lisinopril 10 mg daily
    2. Carvedilol 12.5 mg twice daily
    3. Spironolactone 25 mg daily
    4. Furosemide 40 mg twice daily
    5. Atorvastatin 80 mg daily
    6. Aspirin 81 mg daily
    7. Clopidogrel 75 mg daily
    8. Insulin glargine 20 units nightly
    9. Insulin lispro sliding scale before meals

    DISCHARGE PLAN:
    1. Follow-up with cardiology in 2 weeks
    2. Follow-up with primary care physician in 1 week
    3. Follow-up with nephrology in 3 weeks
    4. Daily weights, 2 gram sodium diet, fluid restriction to 1.5 liters daily
    """

    # Run the ICD-10 coding swarm
    result = create_icd10_coding_swarm(clinical_documentation)

    # Print and save the result
    print(json.dumps(result, indent=4))
    return result


if __name__ == "__main__":
    run_example_icd10_coding()

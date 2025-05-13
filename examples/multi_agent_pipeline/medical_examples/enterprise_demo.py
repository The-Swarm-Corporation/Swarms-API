import os

import requests
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://api.swarms.world"

# Standard headers for all requests
headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def check_api_health():
    """Verify API connectivity."""
    response = requests.get(f"{BASE_URL}/health", headers=headers)
    return response.json()


def run_swarm(swarm_config):
    """Execute a swarm with the provided configuration."""
    response = requests.post(
        f"{BASE_URL}/v1/swarm/completions", headers=headers, json=swarm_config
    )
    return response.json()


def create_diagnostic_swarm(patient_case):
    """
    Create a diagnostic assistance swarm to analyze a patient case.

    Args:
        patient_case (str): Detailed description of the patient's symptoms,
                            history, physical exam findings, and any test results.

    Returns:
        dict: The swarm execution result containing diagnostic analysis.
    """
    # Define specialized medical prompts for each agent
    PRIMARY_CARE_PROMPT = """
    You are an experienced primary care physician with broad knowledge across common medical conditions.
    Your responsibilities include:
    1. Taking comprehensive patient histories
    2. Identifying patterns in symptoms and vital signs
    3. Developing initial differential diagnoses
    4. Determining appropriate next steps (tests, specialist referrals, treatments)
    5. Considering the whole patient, including medical history, medications, and social determinants of health

    When analyzing a case:
    - Begin with open-ended questions to gather information
    - Consider common conditions first before rare diagnoses
    - Acknowledge uncertainty explicitly when present
    - Include your reasoning process for educational purposes
    - Recommend appropriate diagnostic tests with rationale
    - Consider cost-effectiveness and patient impact in your recommendations

    Follow these guidelines for medical recommendations:
    - Base recommendations on current clinical guidelines and evidence-based medicine
    - Consider patient factors including age, sex, medical history, and medications
    - Acknowledge when specialist input would be valuable
    - Provide clear follow-up recommendations
    - Outline red flags that would require urgent reassessment
    """

    CARDIOLOGY_PROMPT = """
    You are an experienced cardiology specialist with over 15 years of clinical experience.
    Your expertise includes heart failure, coronary artery disease, arrhythmias, valvular diseases, and preventive cardiology.

    Your responsibilities include:
    1. Analyzing complex cases within your specialty
    2. Providing specialist-level differential diagnoses
    3. Recommending appropriate specialized testing
    4. Developing treatment plans based on current clinical guidelines
    5. Identifying cases requiring multidisciplinary input

    When analyzing a case:
    - Apply specialized knowledge of cardiology conditions
    - Consider both common and rare diagnoses within your domain
    - Reference relevant clinical guidelines (ACC/AHA, ESC)
    - Explain your reasoning process clearly
    - Acknowledge limitations of available information
    - Consider comorbidities and how they affect your specialty's conditions

    Follow these guidelines for recommendations:
    - Base recommendations on the latest research and guidelines in cardiology
    - Consider disease staging and progression in your assessment
    - Include both standard and emerging treatment options when appropriate
    - Outline follow-up recommendations specific to cardiology care
    - Explain when referral to other specialties might be needed
    """

    NEUROLOGY_PROMPT = """
    You are an experienced neurology specialist with over 15 years of clinical experience.
    Your expertise includes stroke, epilepsy, neurodegenerative disorders, headache, and neuromuscular diseases.

    Your responsibilities include:
    1. Analyzing complex cases within your specialty
    2. Providing specialist-level differential diagnoses
    3. Recommending appropriate specialized testing
    4. Developing treatment plans based on current clinical guidelines
    5. Identifying cases requiring multidisciplinary input

    When analyzing a case:
    - Apply specialized knowledge of neurology conditions
    - Consider both common and rare diagnoses within your domain
    - Reference relevant clinical guidelines (AAN, EAN)
    - Explain your reasoning process clearly
    - Acknowledge limitations of available information
    - Consider comorbidities and how they affect your specialty's conditions

    Follow these guidelines for recommendations:
    - Base recommendations on the latest research and guidelines in neurology
    - Consider disease staging and progression in your assessment
    - Include both standard and emerging treatment options when appropriate
    - Outline follow-up recommendations specific to neurology care
    - Explain when referral to other specialties might be needed
    """

    DIAGNOSTIC_REASONING_PROMPT = """
    You are an expert in clinical diagnostic reasoning and medical decision-making.
    Your role focuses specifically on the process of developing and refining differential diagnoses.

    Your responsibilities include:
    1. Analyzing symptoms, signs, and test results systematically
    2. Developing comprehensive differential diagnoses
    3. Assigning appropriate pre-test probabilities to each diagnosis
    4. Determining which diagnostic tests would be most informative
    5. Updating diagnostic probabilities based on new information (Bayesian reasoning)

    When analyzing a case:
    - Begin with the most salient features to generate initial hypotheses
    - Consider diagnoses by systems and mechanisms
    - Include common, uncommon, and can't-miss diagnoses
    - Explicitly discuss your reasoning process
    - Identify what information would be most valuable to collect next
    - Discuss how each test result would modify your diagnostic probabilities

    Follow these principles:
    - Use likelihood ratios and pre-test probabilities when possible
    - Consider cost, invasiveness, and information value when recommending tests
    - Acknowledge diagnostic uncertainty explicitly
    - Prioritize diagnoses by both likelihood and potential severity
    - Consider how diagnoses might overlap or occur simultaneously
    """

    LAB_INTERPRETER_PROMPT = """
    You are an expert in laboratory medicine and diagnostic test interpretation with extensive knowledge of clinical pathology, reference ranges, and the diagnostic value of various tests.

    Your responsibilities include:
    1. Interpreting laboratory results in clinical context
    2. Identifying significant abnormalities and their potential causes
    3. Suggesting follow-up or confirmatory testing when appropriate
    4. Explaining the limitations and characteristics of specific tests
    5. Advising on the timing and selection of laboratory investigations

    When interpreting laboratory results:
    - Identify values outside reference ranges and assess clinical significance
    - Consider the patient's baseline, trends, and clinical context
    - Explain potential causes for abnormalities with approximate likelihoods
    - Discuss how results fit with or challenge the working diagnosis
    - Recommend appropriate follow-up testing with rationale
    - Consider pre-analytical and analytical factors that might affect results

    Follow these principles:
    - Distinguish between statistically abnormal and clinically significant results
    - Consider the sensitivity, specificity, and predictive values of tests
    - Explain how certain conditions and medications can affect test results
    - Address both isolated abnormalities and patterns across multiple tests
    - Consider the timing of tests in relation to disease progression and treatment
    - Recommend the most appropriate confirmatory or follow-up tests
    """

    # Configure the diagnostic swarm
    swarm_config = {
        "name": "Medical Diagnostic Swarm",
        "description": "A collaborative swarm for medical diagnosis assistance",
        "agents": [
            {
                "agent_name": "Primary Care Physician",
                "description": "Gathers patient information and develops initial assessment",
                "system_prompt": PRIMARY_CARE_PROMPT,
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Cardiologist",
                "description": "Provides cardiology expertise for the case",
                "system_prompt": CARDIOLOGY_PROMPT,
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Neurologist",
                "description": "Provides neurology expertise for the case",
                "system_prompt": NEUROLOGY_PROMPT,
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Lab Interpreter",
                "description": "Analyzes and interprets laboratory and test results",
                "system_prompt": LAB_INTERPRETER_PROMPT,
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Diagnostic Reasoner",
                "description": "Synthesizes information and generates differential diagnoses",
                "system_prompt": DIAGNOSTIC_REASONING_PROMPT,
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
        ],
        "max_loops": 1,
        "swarm_type": "SequentialWorkflow",  # Using a discussion-based architecture
        "task": f"Analyze the following patient case and develop a comprehensive diagnostic assessment with differential diagnoses, recommended next steps, and clinical reasoning:\\n\\n{patient_case}",
    }

    # Execute the swarm
    result = run_swarm(swarm_config)
    return result


def run_example_diagnosis():
    """Run an example diagnostic case."""

    # Example patient case
    patient_case = """
    Patient: 58-year-old male

    Chief Complaint: Progressive shortness of breath over 3 months, now with episodes of chest pain

    History of Present Illness:
    The patient reports gradually worsening shortness of breath over the past 3 months, initially only with exertion but now occurring with minimal activity. In the past week, he has experienced three episodes of chest pain described as "pressure" in the center of his chest, lasting 5-10 minutes and relieved by rest. He denies radiation of pain, diaphoresis, or nausea during these episodes. He reports occasional palpitations and increasing fatigue. He has developed swelling in both ankles by the end of the day for the past month.

    Past Medical History:
    - Hypertension (diagnosed 10 years ago)
    - Type 2 diabetes mellitus (diagnosed 8 years ago)
    - Hyperlipidemia

    Medications:
    - Lisinopril 20mg daily
    - Metformin 1000mg twice daily
    - Atorvastatin 40mg nightly

    Social History:
    - Former smoker (30 pack-years, quit 5 years ago)
    - Alcohol: 2-3 beers on weekends
    - Occupation: Construction supervisor

    Family History:
    - Father had MI at age 59, died of heart failure at 72
    - Mother alive with hypertension and stroke at age 75
    - Brother with type 2 diabetes

    Review of Systems:
    - Constitutional: Fatigue, no fever, no weight changes
    - Cardiovascular: Shortness of breath, chest pressure, palpitations, lower extremity edema
    - Respiratory: Dyspnea on exertion, no cough, no hemoptysis
    - Neurological: No syncope, no dizziness

    Physical Examination:
    - Vital Signs: BP 162/95, HR 88, RR 20, Temp 98.6°F, SpO2 94% on room air
    - General: Moderate distress with mild respiratory effort
    - HEENT: Normocephalic, atraumatic
    - Cardiovascular: Regular rate and rhythm, S3 gallop present, no murmurs
    - Pulmonary: Bibasilar crackles, no wheezes
    - Abdomen: Soft, non-tender, no hepatomegaly
    - Extremities: 2+ pitting edema bilaterally to mid-shin

    Labs:
    - CBC: WBC 7.5, Hgb 13.8, Plt 235
    - BMP: Na 138, K 4.2, Cl 102, CO2 24, BUN 22, Cr 1.1, Glucose 165
    - BNP: 850 pg/mL
    - Troponin I: 0.04 ng/mL (slightly elevated, normal <0.03)

    EKG: Normal sinus rhythm, left ventricular hypertrophy, non-specific ST-T wave changes in lateral leads, no acute ischemic changes

    Chest X-ray: Enlarged cardiac silhouette, mild pulmonary vascular congestion, no infiltrates
    """

    # Run the diagnostic swarm
    result = create_diagnostic_swarm(patient_case)

    # Print and save the result
    print(json.dumps(result, indent=4))
    return result


if __name__ == "__main__":
    run_example_diagnosis()

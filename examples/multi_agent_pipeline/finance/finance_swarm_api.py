import json
import os

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv("SWARMS_API_KEY")
BASE_URL = "https://api.swarms.world"

# Standard headers for all requests
headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}


def run_swarm(swarm_config):
    """Execute a swarm with the provided configuration."""
    response = requests.post(
        f"{BASE_URL}/v1/swarm/completions", headers=headers, json=swarm_config
    )
    return response.json()


def create_quant_analysis_swarm(financial_data):
    """
    Create a swarm for quantitative financial analysis and risk assessment.

    Args:
        financial_data (str): Financial data, market conditions, or trading signals

    Returns:
        dict: The swarm execution result containing analysis and risk metrics.
    """
    # Define specialized prompts for quantitative analysis
    DATA_ANALYZER_PROMPT = """
    You are a quantitative data analyst specializing in financial markets. Your role is to analyze financial data to identify patterns, trends, and potential trading opportunities.

    Your tasks include:
    1. Analyzing price movements and volume patterns
    2. Identifying technical indicators and their signals
    3. Evaluating market sentiment and momentum
    4. Detecting statistical arbitrage opportunities
    5. Analyzing correlation patterns across assets
    6. Identifying market regime changes

    When analyzing data:
    - Focus on statistical significance of patterns
    - Note any unusual market behavior or anomalies
    - Identify potential leading indicators
    - Consider multiple timeframes in your analysis
    - Highlight areas requiring deeper investigation
    """

    RISK_QUANT_PROMPT = """
    You are an expert risk quantitative analyst with extensive experience in risk modeling and assessment.
    Your responsibility is to evaluate potential risks and calculate relevant risk metrics.

    Your tasks include:
    1. Calculating Value at Risk (VaR) metrics
    2. Analyzing portfolio volatility and correlations
    3. Assessing market risk exposure
    4. Evaluating counterparty risk
    5. Calculating stress test scenarios
    6. Analyzing tail risk events

    When assessing risk:
    - Calculate both historical and forward-looking metrics
    - Consider multiple risk factors
    - Apply appropriate risk models based on market conditions
    - Identify potential model limitations
    - Account for liquidity risk
    - Consider systemic risk factors
    """

    STRATEGY_VALIDATOR_PROMPT = """
    You are a senior quantitative strategist responsible for validating trading strategies and risk models.
    Your role is to review proposed analyses and ensure robustness of conclusions.

    Your responsibilities include:
    1. Validating statistical significance of findings
    2. Checking for overfitting in models
    3. Assessing strategy capacity and scalability
    4. Evaluating transaction costs and market impact
    5. Testing strategy robustness across different regimes

    When reviewing analyses:
    - Verify statistical validity of conclusions
    - Check for potential biases in the analysis
    - Validate assumptions in risk models
    - Consider market microstructure effects
    - Identify potential implementation challenges
    - Assess strategy decay risk
    """

    # Configure the quantitative analysis swarm
    swarm_config = {
        "name": "Quantitative Analysis Assistant",
        "description": "A specialized swarm for financial analysis and risk assessment",
        "agents": [
            {
                "agent_name": "Data Analyzer",
                "description": "Analyzes financial data and identifies patterns",
                "system_prompt": DATA_ANALYZER_PROMPT,
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Risk Quantitative Analyst",
                "description": "Calculates risk metrics and assesses exposures",
                "system_prompt": RISK_QUANT_PROMPT,
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
            {
                "agent_name": "Strategy Validator",
                "description": "Reviews analysis and validates conclusions",
                "system_prompt": STRATEGY_VALIDATOR_PROMPT,
                "model_name": "gpt-4o",
                "role": "worker",
                "max_loops": 1,
                "max_tokens": 8192,
                "temperature": 0.5,
                "auto_generate_prompt": False,
            },
        ],
        "max_loops": 1,
        "swarm_type": "SequentialWorkflow",
        "task": f"""
        Analyze the following financial data and provide comprehensive analysis:

        {financial_data}

        For the analysis, provide:
        1. Key market patterns and trends identified
        2. Risk metrics and exposure analysis
        3. Trading strategy recommendations
        4. Implementation considerations
        5. Risk management guidelines

        Also identify any areas where additional data or analysis could improve the conclusions.
        """,
    }

    # Execute the swarm
    result = run_swarm(swarm_config)
    return result


def run_example_quant_analysis():
    """Run an example quantitative analysis case."""

    # Example financial data
    financial_data = """
    MARKET ANALYSIS DATA

    Asset: S&P 500 E-mini Futures
    Date Range: Last 30 days
    
    PRICE DATA:
    - Current Price: 4,780
    - 30-day High: 4,850
    - 30-day Low: 4,680
    - Average Daily Volume: 2.1M contracts
    
    VOLATILITY METRICS:
    - 30-day Historical Volatility: 15.2%
    - VIX Index: 14.5
    - Implied Volatility (ATM): 16.1%
    
    CORRELATION DATA:
    - Correlation with US 10Y Yields: -0.35
    - Correlation with EUR/USD: 0.28
    - Correlation with Gold: -0.12
    
    MARKET CONDITIONS:
    - Fed Funds Rate: 5.25-5.50%
    - US 10Y Yield: 4.12%
    - Recent Fed Statement: Hawkish
    - Market Sentiment Indicators: Mixed
    """

    # Run the quantitative analysis swarm
    result = create_quant_analysis_swarm(financial_data)

    # Print and save the result
    print(json.dumps(result, indent=4))
    return result


if __name__ == "__main__":
    run_example_quant_analysis()

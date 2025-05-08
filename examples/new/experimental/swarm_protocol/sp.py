"""
Example usage of the Swarm Protocol framework with tools, agents, and swarms.
"""

import random
from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from experimental.swarm_protocol.test import SwarmProtocol

# Initialize the Swarm Protocol wrapper
swarm_app = SwarmProtocol(app_name="Financial Analysis Swarm API", version="1.0.0")


# Define input/output models
class StockNewsInput(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    days: int = Field(7, description="Number of days of news to fetch")
    include_sentiment: bool = Field(
        False, description="Whether to include sentiment analysis"
    )


class StockPriceInput(BaseModel):
    symbol: str = Field(..., description="Stock symbol (e.g., AAPL)")
    timeframe: str = Field(
        "1d", description="Timeframe for price data (1d, 5d, 1mo, 3mo, 6mo, 1y)"
    )


class FinancialAnalysisInput(BaseModel):
    symbol: str = Field(..., description="Stock symbol to analyze")
    include_news: bool = Field(True, description="Whether to include news in analysis")
    include_technical: bool = Field(
        True, description="Whether to include technical indicators"
    )


# Example Tools
@swarm_app.tool(description="Fetch recent news for a stock symbol")
def fetch_stock_news(
    symbol: str, days: int = 7, include_sentiment: bool = False
) -> List[Dict]:
    """
    Fetch recent news articles for a given stock symbol.

    Args:
        symbol: Stock ticker symbol (e.g., AAPL)
        days: Number of days of news to fetch
        include_sentiment: Whether to include sentiment analysis with each article

    Returns:
        List of news articles with title, date, source, and optional sentiment
    """
    # In a real implementation, this would call a news API
    # This is a mock implementation for demonstration
    news = [
        {
            "title": f"{symbol} Announces Record Quarterly Results",
            "date": (datetime.now().isoformat()),
            "source": "Financial Times",
            "url": f"https://example.com/news/{symbol}/1",
        },
        {
            "title": f"Analysts Upgrade {symbol} Rating to Strong Buy",
            "date": (datetime.now().isoformat()),
            "source": "Wall Street Journal",
            "url": f"https://example.com/news/{symbol}/2",
        },
        {
            "title": f"New Product Launch Boosts {symbol} Stock",
            "date": (datetime.now().isoformat()),
            "source": "Bloomberg",
            "url": f"https://example.com/news/{symbol}/3",
        },
    ]

    # Add sentiment if requested
    if include_sentiment:
        for article in news:
            article["sentiment"] = random.choice(["positive", "neutral", "negative"])
            article["sentiment_score"] = round(random.uniform(-1.0, 1.0), 2)

    return news


@swarm_app.tool(description="Fetch stock price data")
def fetch_stock_price(symbol: str, timeframe: str = "1d") -> Dict:
    """
    Fetch stock price data for a given symbol and timeframe.

    Args:
        symbol: Stock ticker symbol (e.g., AAPL)
        timeframe: Timeframe for price data (1d, 5d, 1mo, 3mo, 6mo, 1y)

    Returns:
        Dictionary with price data including open, high, low, close, volume
    """
    # Mock implementation
    base_price = random.uniform(50.0, 500.0)
    price_data = {
        "symbol": symbol,
        "timeframe": timeframe,
        "currency": "USD",
        "open": round(base_price, 2),
        "high": round(base_price * random.uniform(1.01, 1.05), 2),
        "low": round(base_price * random.uniform(0.95, 0.99), 2),
        "close": round(base_price * random.uniform(0.98, 1.03), 2),
        "volume": random.randint(1000000, 10000000),
        "timestamp": datetime.now().isoformat(),
    }

    return price_data


@swarm_app.tool(description="Calculate technical indicators for a stock")
def calculate_technical_indicators(
    symbol: str, price_data: Optional[Dict] = None
) -> Dict:
    """
    Calculate technical indicators for a stock based on its price data.

    Args:
        symbol: Stock ticker symbol (e.g., AAPL)
        price_data: Optional price data dictionary (if not provided, will be fetched)

    Returns:
        Dictionary with technical indicators like RSI, MACD, etc.
    """
    # If price data not provided, fetch it
    if price_data is None:
        price_data = fetch_stock_price(symbol)

    # Mock implementation of technical indicators
    indicators = {
        "symbol": symbol,
        "rsi_14": round(random.uniform(30, 70), 2),
        "macd": round(random.uniform(-5, 5), 2),
        "macd_signal": round(random.uniform(-5, 5), 2),
        "bollinger_upper": round(price_data["high"] * 1.05, 2),
        "bollinger_middle": round((price_data["high"] + price_data["low"]) / 2, 2),
        "bollinger_lower": round(price_data["low"] * 0.95, 2),
        "sma_50": round(price_data["close"] * random.uniform(0.9, 1.1), 2),
        "sma_200": round(price_data["close"] * random.uniform(0.85, 1.15), 2),
        "timestamp": datetime.now().isoformat(),
    }

    return indicators


# Example Agent
@swarm_app.agent(
    description="Financial analysis agent that combines news and technical data"
)
def financial_analyst_agent(
    symbol: str, include_news: bool = True, include_technical: bool = True
) -> Dict:
    """
    Comprehensive financial analysis agent that combines multiple data sources.

    Args:
        symbol: Stock ticker symbol to analyze
        include_news: Whether to include news in analysis
        include_technical: Whether to include technical indicators

    Returns:
        Comprehensive analysis of the stock including price, technical indicators, news, and recommendations
    """
    # Get base price data
    price_data = fetch_stock_price(symbol)

    # Build analysis
    analysis = {
        "symbol": symbol,
        "price_data": price_data,
        "timestamp": datetime.now().isoformat(),
    }

    # Add technical indicators if requested
    if include_technical:
        analysis["technical_indicators"] = calculate_technical_indicators(
            symbol, price_data
        )

    # Add news if requested
    if include_news:
        analysis["news"] = fetch_stock_news(symbol, days=3, include_sentiment=True)

    # Generate mock recommendation
    if include_technical:
        rsi = analysis["technical_indicators"]["rsi_14"]
        if rsi < 30:
            recommendation = "BUY"
            reasoning = f"RSI ({rsi}) indicates the stock is oversold"
        elif rsi > 70:
            recommendation = "SELL"
            reasoning = f"RSI ({rsi}) indicates the stock is overbought"
        else:
            recommendation = "HOLD"
            reasoning = f"RSI ({rsi}) is in neutral territory"
    else:
        recommendation = "HOLD"
        reasoning = "Insufficient technical data for recommendation"

    analysis["recommendation"] = {
        "action": recommendation,
        "reasoning": reasoning,
        "confidence": round(random.uniform(0.6, 0.9), 2),
    }

    return analysis


# Example Swarm
@swarm_app.swarm(
    description="Portfolio analysis swarm that coordinates multiple agents and tools"
)
def portfolio_analysis_swarm(symbols: List[str], detailed: bool = False) -> Dict:
    """
    Analyze an entire portfolio of stocks by coordinating multiple agents and tools.

    Args:
        symbols: List of stock symbols in the portfolio
        detailed: Whether to include detailed analysis for each stock

    Returns:
        Portfolio analysis with individual stock analyses and overall recommendations
    """
    # Initialize result structure
    portfolio_analysis = {
        "timestamp": datetime.now().isoformat(),
        "symbols_analyzed": len(symbols),
        "stocks": {},
        "portfolio_summary": {},
    }

    # Analyze each stock in the portfolio
    for symbol in symbols:
        # Use the financial analyst agent for each stock
        stock_analysis = financial_analyst_agent(
            symbol=symbol, include_news=detailed, include_technical=True
        )

        # Store full analysis or just the summary based on detailed flag
        if detailed:
            portfolio_analysis["stocks"][symbol] = stock_analysis
        else:
            portfolio_analysis["stocks"][symbol] = {
                "price": stock_analysis["price_data"]["close"],
                "recommendation": stock_analysis["recommendation"]["action"],
                "confidence": stock_analysis["recommendation"]["confidence"],
            }

    # Generate portfolio summary
    buy_count = sum(
        1
        for s in portfolio_analysis["stocks"].values()
        if isinstance(s, dict)
        and s.get("recommendation", {}).get("action") == "BUY"
        or s.get("recommendation") == "BUY"
    )
    sell_count = sum(
        1
        for s in portfolio_analysis["stocks"].values()
        if isinstance(s, dict)
        and s.get("recommendation", {}).get("action") == "SELL"
        or s.get("recommendation") == "SELL"
    )
    hold_count = sum(
        1
        for s in portfolio_analysis["stocks"].values()
        if isinstance(s, dict)
        and s.get("recommendation", {}).get("action") == "HOLD"
        or s.get("recommendation") == "HOLD"
    )

    portfolio_analysis["portfolio_summary"] = {
        "buy_recommendations": buy_count,
        "sell_recommendations": sell_count,
        "hold_recommendations": hold_count,
        "overall_sentiment": (
            "Bullish"
            if buy_count > sell_count
            else "Bearish" if sell_count > buy_count else "Neutral"
        ),
    }

    return portfolio_analysis


# Run the API if this file is executed directly
if __name__ == "__main__":
    print("Starting Swarm Protocol API...")
    swarm_app.run(port=8000, workers=4)

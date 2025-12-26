#!/bin/bash

# Base URL
BASE="http://localhost:8000/api"

echo "=== Testing Cluster E Endpoints ==="

echo -e "\n1. Fundamentals (E7) - AAPL"
curl -s "$BASE/fundamentals/AAPL?compact=true" | cut -c 1-100
echo "..."

echo -e "\n2. Risk Score (E2)"
curl -s -X POST "$BASE/research/e/risk_score" -H "Content-Type: application/json" -d '{"lookback_days": 252}' | cut -c 1-100
echo "..."

echo -e "\n3. Narrative (E1)"
curl -s -X POST "$BASE/research/e/narrative" -H "Content-Type: application/json" -d '{"market_proxy": "SPY", "lookback_days": 60}' | cut -c 1-100
echo "..."

echo -e "\n4. Market Sentiment (E9)"
curl -s "$BASE/sentiment/market?tickers=SPY,QQQ&lookback=30" | cut -c 1-100
echo "..."

echo -e "\n5. Asset Sentiment (E9) - AAPL"
curl -s "$BASE/sentiment/asset?ticker=AAPL&lookback=90" | cut -c 1-100
echo "..."

echo -e "\n6. Sharpe Radar (E6)"
curl -s -X POST "$BASE/research/e/sharpe_radar" -H "Content-Type: application/json" -d '{"tickers": ["SPY", "QQQ"], "horizons": [21, 63]}' | cut -c 1-100
echo "..."

echo -e "\n7. Spider Chart (E10)"
curl -s -X POST "$BASE/research/e/spider" -H "Content-Type: application/json" -d '{"ref": "SPY", "tickers": ["SPY", "QQQ", "GLD"], "window": 60}' | cut -c 1-100
echo "..."

echo -e "\n8. Pattern Scanner (E5)"
curl -s -X POST "$BASE/research/e/scan" -H "Content-Type: application/json" -d '{"pattern": "rsi_oversold", "limit": 5, "tickers": ["SPY", "QQQ"]}' | cut -c 1-100
echo "..."

echo -e "\n9. Market Replay (E4)"
curl -s -X POST "$BASE/research/e/replay" -H "Content-Type: application/json" -d '{"mode": "preset", "preset": "covid", "assets": ["SPY"]}' | cut -c 1-100
echo "..."

echo -e "\n=== Verification Complete ==="

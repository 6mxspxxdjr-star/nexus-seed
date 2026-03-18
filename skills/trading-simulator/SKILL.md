# trading-simulator

## Description
Runs MiroFish economic simulations using real crypto market data from CoinGecko.
Backtests trading strategies and evaluates ROI, risk, and Sharpe ratio.

## Prerequisites
- MiroFish installed in ~/nexus/simulations/
- Ollama running with qwen2.5 model
- Internet access for CoinGecko API (free tier, no key required)

## Parameters
- `coin` (optional, default="bitcoin"): CoinGecko coin ID
- `days` (optional, default=30): Historical data lookback period
- `strategy` (optional, default="momentum"): Strategy to test (momentum, mean-reversion, breakout)
- `agents` (optional, default=200): Number of simulation agents
- `capital` (optional, default=10000): Starting capital per agent

## Usage
```bash
./run --coin ethereum --days 90 --strategy mean-reversion --agents 500
./run  # Uses defaults: bitcoin, 30 days, momentum, 200 agents
```

## Returns
JSON with: strategy_name, coin, roi_mean, roi_std, sharpe_ratio, max_drawdown, win_rate, best_params

## Notes
- No real money is ever used — this is simulation only
- Results are stored in memory for the Evolution agent to optimize
- The Strategist can use results to recommend strategies to the user

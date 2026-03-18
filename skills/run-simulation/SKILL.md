# run-simulation

## Description
Launch a MiroFish simulation with specified parameters. Runs the multi-agent
economic simulation engine, captures results, and stores outcomes in memory.

## Parameters
- `agents` (optional, default=100): Number of simulation agents
- `rounds` (optional, default=50): Number of simulation rounds
- `market` (optional, default="crypto"): Market type (crypto, real-estate, general)
- `strategy` (optional): Strategy file to test
- `params` (optional): JSON string of additional simulation parameters

## Usage
```bash
./run --agents 200 --rounds 100 --market crypto
./run --strategy strategies/momentum.json --agents 500
```

## Returns
JSON object with: simulation_id, status, summary (win_rate, roi, sharpe_ratio), duration, memory_id

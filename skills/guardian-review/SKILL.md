# guardian-review

## Description
Submit a proposed action for Guardian triple-check review. For high-stakes
decisions, the Guardian also consults a cloud model (Anthropic/OpenAI) for
independent verification.

## Parameters
- `proposal` (required): Description of the proposed action
- `action` (optional): Action category (create-agent, financial, system-mod, external-api)
- `risk` (optional, default="medium"): Risk level (low, medium, high, critical)
- `context` (optional): Additional context for the review
- `skip_cloud` (optional, default=false): Skip cloud model verification (for low-risk only)

## Usage
```bash
./run "Deploy new trading strategy with 5% portfolio allocation" --action financial --risk high
./run "Install new Python package: requests" --action system-mod --risk low --skip_cloud
```

## Returns
YAML-formatted decision: decision (APPROVED/REJECTED/ESCALATE), confidence, reasoning, conditions

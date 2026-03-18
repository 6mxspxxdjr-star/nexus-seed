# create-agent

## Description
Create a new agent with a defined identity and register it with OpenClaw.
Requires Guardian approval for all new agent creations.

## Parameters
- `name` (required): Agent name (lowercase, alphanumeric + hyphens)
- `role` (required): One-line role description
- `directives` (required): Core directives (newline-separated)
- `capabilities` (optional): List of capabilities
- `boundaries` (optional): List of restrictions

## Usage
```bash
./run --name "research-analyst" \
      --role "Researches market trends and competitive intelligence" \
      --directives "Focus on accuracy\nCite all sources\nFlag low-confidence findings"
```

## Returns
JSON object with: agent_id, status, identity_path, registration_status

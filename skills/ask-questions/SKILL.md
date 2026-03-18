# ask-questions

## Description
Query the local LLM (via Ollama) with context from Nexus memory.
Combines RAG (retrieval-augmented generation) with the local model.

## Parameters
- `question` (required): The question to answer
- `context_query` (optional): Custom memory search query for context (defaults to the question)
- `model` (optional, default="qwen2.5:14b"): Ollama model to use
- `max_context` (optional, default=5): Number of memory results to include as context

## Usage
```bash
./run "What is the best performing profit engine this week?"
./run "Explain the current trading strategy" --model qwen2.5:7b --max_context 10
```

## Returns
JSON object with: answer, sources (memory IDs used as context), model, tokens_used

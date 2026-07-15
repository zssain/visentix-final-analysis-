# Data Handling Policy — LLM Endpoint Usage

## Hosted Endpoint Requirements

When sending privacy notice text to a hosted model endpoint:

1. **Zero-retention / No-training**: The provider MUST be configured for zero data
   retention and must NOT use customer data for model training. This is set via
   the `HOSTED_QWEN_BASE_URL` environment variable — choose a provider that
   contractually guarantees this (e.g. Together AI, Fireworks AI, Azure AI with
   data processing agreements).

2. **Minimize what is sent**: Only the specific clause text needed for classification
   or phrasing is sent. Never send entire notices, multiple clauses in one call,
   or any metadata (org names, user IDs).

3. **Logging**: The system logs THAT text was sent (timestamp, character count,
   task type) but NEVER logs the actual text content. API keys are never logged.

4. **Local alternative**: For batch processing and development, the local Ollama
   endpoint (`OLLAMA_BASE_URL`) is used. No data leaves the machine in this mode.

## Environment Variables

| Variable | Purpose | Security |
|---|---|---|
| `HOSTED_QWEN_BASE_URL` | Hosted endpoint URL | Not a secret |
| `HOSTED_QWEN_API_KEY` | API authentication | SECRET — .env only |
| `HOSTED_QWEN_MODEL` | Model identifier | Not a secret |
| `OLLAMA_BASE_URL` | Local endpoint | localhost only |

## What the LLM Does and Does NOT Do

- **DOES**: Classify clause text into taxonomy domains. Smooth pre-computed
  findings/recommendations into professional language.
- **DOES NOT**: Compute scores, generate findings, create recommendations,
  make legal judgments, or produce any number that isn't pre-computed by the
  formula engine.

See AGENTS.md §2 for the full intelligence philosophy.

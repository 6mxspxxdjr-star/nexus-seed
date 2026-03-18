# lead-generator

## Description
Generates real estate leads by scraping property data (via Apify/Zillow) and
enriching with skip-trace data (via REISkip). Requires API keys on first use.

## Prerequisites
- Apify API key (for Zillow scraping)
- REISkip API key (for skip-tracing)
- Keys are prompted on first use and stored securely in configs/

## Parameters
- `location` (required): City, state or ZIP code
- `property_type` (optional, default="single-family"): Property type filter
- `max_results` (optional, default=50): Maximum leads to generate
- `skip_trace` (optional, default=true): Whether to run skip-tracing
- `filters` (optional): JSON string of additional filters (price range, equity, etc.)

## Usage
```bash
./run --location "Austin, TX" --max_results 100 --property_type multi-family
./run --location "90210" --filters '{"min_equity_pct": 40, "max_price": 500000}'
```

## Returns
JSON with: leads (array), total_found, skip_traced_count, cost_estimate

## Notes
- Apify free tier: 5 USD/month of compute
- REISkip charges per skip-trace (~$0.15/record)
- Cost estimates are shown before execution; user must confirm

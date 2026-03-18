# content-creator

## Description
Generates blog posts and articles using the local LLM, with optional
scheduling to WordPress. Fully offline content generation — publishing
requires WordPress API credentials.

## Prerequisites
- Ollama running with qwen2.5 model
- WordPress REST API credentials (optional, for publishing)

## Parameters
- `topic` (required): Topic or title for the content
- `style` (optional, default="informative"): Writing style (informative, persuasive, tutorial, listicle)
- `length` (optional, default="medium"): Content length (short=500w, medium=1000w, long=2000w)
- `publish` (optional, default=false): Whether to publish to WordPress
- `schedule` (optional): ISO datetime to schedule publication
- `seo_keywords` (optional): Comma-separated SEO keywords to target

## Usage
```bash
./run --topic "5 Ways to Automate Real Estate Lead Generation" --style listicle --length medium
./run --topic "Crypto Market Analysis" --publish --schedule "2026-03-20T09:00:00"
```

## Returns
JSON with: title, content (markdown), word_count, seo_score, published (bool), url (if published)

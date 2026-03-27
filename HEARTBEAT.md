# LeadFlow Heartbeat Tasks

## Every 30 minutes:
- Check /api/call-queue for stale leads (no contact in 7+ days) and flag them
- Verify lead data quality: leads missing phone AND email AND website should be flagged with priority=low

## Daily (run once):
- Deduplication audit: find leads with same phone number, merge or flag
- Post daily summary to #outreach: X leads in pipeline, X follow-ups due today, X closed this month

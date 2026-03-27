# Discord Integration Setup

## 1. Create a Discord Webhook

1. Open your Discord server
2. Go to **Server Settings → Integrations → Webhooks**
3. Click **New Webhook**
4. Name it `LeadFlow`, pick the channel you want notifications in
5. Click **Copy Webhook URL**
6. Save this URL — you'll need it for the env vars below

## 2. Set Environment Variables

### Local development (`.env.local`)
```
DISCORD_INGEST_SECRET=leadflow-discord-2024
SUPABASE_WEBHOOK_SECRET=leadflow-webhook-2024
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN
```

### Vercel (production)
In the Vercel dashboard → your project → **Settings → Environment Variables**, add:

| Name | Value |
|------|-------|
| `DISCORD_INGEST_SECRET` | `leadflow-discord-2024` (or a strong secret) |
| `SUPABASE_WEBHOOK_SECRET` | `leadflow-webhook-2024` (or a strong secret) |
| `DISCORD_WEBHOOK_URL` | Your Discord webhook URL |

## 3. Set Up Supabase DB Webhook

1. In Supabase dashboard → **Database → Webhooks**
2. Click **Create a new hook**
3. Configure:
   - **Name**: `notify-discord`
   - **Table**: `leads`
   - **Events**: `INSERT`, `UPDATE`
   - **Type**: HTTP Request
   - **Method**: POST
   - **URL**: `https://your-domain.vercel.app/api/notify-discord`
   - **Headers**:
     - `Authorization`: `Bearer leadflow-webhook-2024`
     - `Content-Type`: `application/json`
4. Click **Confirm**

## 4. Using the Discord Ingest Endpoint

POST leads from your Discord scraper to `/api/discord-ingest`:

```bash
curl -X POST https://your-domain.vercel.app/api/discord-ingest \
  -H "Authorization: Bearer leadflow-discord-2024" \
  -H "Content-Type: application/json" \
  -d '{
    "leads": [
      {
        "company_name": "Acme Roofing",
        "contact_name": "John Smith",
        "phone": "555-123-4567",
        "city": "Austin",
        "state": "TX",
        "zip": "78701",
        "service_type": "roofing"
      }
    ]
  }'
```

Response:
```json
{ "inserted": 1, "duplicates": 0, "leads": [...] }
```

Duplicates are detected by:
- Matching phone number (if provided), OR
- Matching company_name + zip code

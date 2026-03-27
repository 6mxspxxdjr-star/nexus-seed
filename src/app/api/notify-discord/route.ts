import { NextRequest } from 'next/server'

interface Lead {
  id: string
  company_name: string
  contact_name?: string | null
  phone?: string | null
  email?: string | null
  city?: string | null
  state?: string | null
  zip?: string | null
  status?: string | null
  estimated_deal_size?: number | null
  assigned_to?: string | null
  [key: string]: unknown
}

interface SupabaseWebhookPayload {
  type: 'INSERT' | 'UPDATE' | 'DELETE'
  table: string
  record: Lead
  old_record?: Lead | null
  schema: string
}

async function postToDiscord(message: string): Promise<void> {
  const webhookUrl = process.env.DISCORD_WEBHOOK_URL
  if (!webhookUrl) {
    console.error('DISCORD_WEBHOOK_URL is not set')
    return
  }

  try {
    const response = await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: message, username: 'LeadFlow' }),
    })

    if (!response.ok) {
      console.error(`Discord webhook failed: ${response.status} ${await response.text()}`)
    }
  } catch (err) {
    console.error('Discord webhook error:', err)
  }
}

function formatAmount(amount?: number | null): string {
  if (!amount) return '$?'
  return `$${amount.toLocaleString()}`
}

function buildStatusChangeMessage(record: Lead, oldRecord: Lead): string | null {
  const oldStatus = oldRecord.status
  const newStatus = record.status
  const company = record.company_name
  const amount = record.estimated_deal_size

  if (oldStatus === newStatus) return null

  if (oldStatus === 'new' && newStatus === 'contacted') {
    return `📞 ${company} — first contact made`
  }
  if (oldStatus === 'contacted' && newStatus === 'follow_up') {
    return `🔄 ${company} — follow-up scheduled`
  }
  if (newStatus === 'quoted') {
    return `💰 ${company} — quoted ${formatAmount(amount)}`
  }
  if (newStatus === 'closed_won') {
    return `🎉 ${company} — CLOSED! ${formatAmount(amount)}`
  }
  if (newStatus === 'dead') {
    return `💀 ${company} — marked dead`
  }

  return null
}

export async function POST(request: NextRequest) {
  const authHeader = request.headers.get('authorization')
  const secret = process.env.SUPABASE_WEBHOOK_SECRET

  if (!secret || authHeader !== `Bearer ${secret}`) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const payload = await request.json() as SupabaseWebhookPayload

  if (payload.table !== 'leads') {
    return Response.json({ ok: true, skipped: 'not leads table' })
  }

  const { type, record, old_record } = payload

  if (type === 'INSERT') {
    const city = record.city || ''
    const state = record.state || ''
    const location = [city, state].filter(Boolean).join(', ')
    const phone = record.phone || 'no phone'
    const message = `🆕 New lead: ${record.company_name}${location ? ` (${location})` : ''} — ${phone}`
    await postToDiscord(message)
  } else if (type === 'UPDATE' && old_record) {
    const message = buildStatusChangeMessage(record, old_record)
    if (message) {
      await postToDiscord(message)
    }
  }

  return Response.json({ ok: true })
}

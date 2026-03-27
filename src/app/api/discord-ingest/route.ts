import { createAdminClient } from '@/lib/supabase/admin'
import { ingestGoplacesLeads, type GoplacesPlace } from '@/lib/ingest-leads'
import { NextRequest } from 'next/server'

async function postToDiscordOutreach(message: string): Promise<void> {
  const webhookUrl = process.env.DISCORD_WEBHOOK_URL_OUTREACH
  if (!webhookUrl) return
  try {
    await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: message, username: 'LeadFlow' }),
    })
  } catch (err) {
    console.error('Discord outreach webhook error:', err)
  }
}

export async function POST(request: NextRequest) {
  const authHeader = request.headers.get('authorization')
  const secret = process.env.DISCORD_INGEST_SECRET

  if (!secret || authHeader !== `Bearer ${secret}`) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json()
  const supabase = createAdminClient()

  // goplaces format: { places: GoplacesPlace[] }
  if (Array.isArray(body.places)) {
    const places = body.places as GoplacesPlace[]
    if (places.length === 0) {
      return Response.json({ error: 'places array is empty' }, { status: 400 })
    }

    const { inserted, duplicates, skipped_inactive, leads } = await ingestGoplacesLeads(places, supabase)

    if (inserted > 0) {
      await postToDiscordOutreach(
        `📥 Ingested ${inserted} new lead${inserted !== 1 ? 's' : ''} (${duplicates} dupes, ${skipped_inactive} inactive skipped)`
      )
    }

    return Response.json({ inserted, duplicates, skipped_inactive, leads })
  }

  // Legacy format: { leads: LegacyLead[] }
  interface LegacyLead {
    company_name: string
    contact_name?: string
    phone?: string
    email?: string
    city?: string
    state?: string
    zip?: string
    service_type?: string
    notes?: string
  }

  const legacyLeads = body.leads as LegacyLead[] | undefined
  if (!Array.isArray(legacyLeads) || legacyLeads.length === 0) {
    return Response.json({ error: 'places or leads array is required' }, { status: 400 })
  }

  let inserted = 0
  let duplicates = 0
  const insertedLeads: unknown[] = []

  for (const lead of legacyLeads) {
    if (!lead.company_name) continue

    let isDuplicate = false

    if (lead.phone) {
      const { data: phoneMatch } = await supabase
        .from('leads')
        .select('id')
        .eq('phone', lead.phone)
        .maybeSingle()
      if (phoneMatch) isDuplicate = true
    }

    if (!isDuplicate && lead.company_name && lead.city) {
      const { data: nameCityMatch } = await supabase
        .from('leads')
        .select('id')
        .eq('company_name', lead.company_name)
        .eq('city', lead.city)
        .maybeSingle()
      if (nameCityMatch) isDuplicate = true
    }

    if (isDuplicate) {
      duplicates++
      continue
    }

    const { data, error } = await supabase
      .from('leads')
      .insert({
        company_name: lead.company_name,
        contact_name: lead.contact_name || null,
        phone: lead.phone || null,
        email: lead.email || null,
        city: lead.city || null,
        state: lead.state || null,
        zip: lead.zip || null,
        service_type: lead.service_type || null,
        notes: lead.notes || null,
        source: 'discord_scraper',
        status: 'new',
        priority: 'medium',
      })
      .select()
      .single()

    if (error) {
      console.error(`Failed to insert lead ${lead.company_name}:`, error.message)
      continue
    }

    inserted++
    insertedLeads.push(data)
  }

  return Response.json({ inserted, duplicates, leads: insertedLeads })
}

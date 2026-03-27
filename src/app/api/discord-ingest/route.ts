import { createClient } from '@/lib/supabase/server'
import { NextRequest } from 'next/server'

interface IngestLead {
  company_name: string
  contact_name?: string
  phone?: string
  email?: string
  city?: string
  state?: string
  zip?: string
  service_type?: string
  notes?: string
  source?: string
}

export async function POST(request: NextRequest) {
  const authHeader = request.headers.get('authorization')
  const secret = process.env.DISCORD_INGEST_SECRET

  if (!secret || authHeader !== `Bearer ${secret}`) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json()
  const { leads, discord_channel_id: _channel } = body as {
    leads: IngestLead[]
    discord_channel_id?: string
  }

  if (!Array.isArray(leads) || leads.length === 0) {
    return Response.json({ error: 'leads array is required' }, { status: 400 })
  }

  const supabase = await createClient()
  let inserted = 0
  let duplicates = 0
  const insertedLeads: unknown[] = []

  for (const lead of leads) {
    if (!lead.company_name) continue

    // Check for duplicate: phone match OR company_name + zip match
    let isDuplicate = false

    if (lead.phone) {
      const { data: phoneMatch } = await supabase
        .from('leads')
        .select('id')
        .eq('phone', lead.phone)
        .maybeSingle()

      if (phoneMatch) {
        isDuplicate = true
      }
    }

    if (!isDuplicate && lead.company_name && lead.zip) {
      const { data: nameZipMatch } = await supabase
        .from('leads')
        .select('id')
        .eq('company_name', lead.company_name)
        .eq('zip', lead.zip)
        .maybeSingle()

      if (nameZipMatch) {
        isDuplicate = true
      }
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

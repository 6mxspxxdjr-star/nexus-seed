import { createClient } from '@/lib/supabase/server'
import { NextRequest } from 'next/server'

export async function GET() {
  const supabase = await createClient()

  const { data, error } = await supabase
    .from('leads')
    .select('*, profiles(id, full_name, role)')
    .order('created_at', { ascending: false })

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({ leads: data })
}

export async function POST(request: NextRequest) {
  const supabase = await createClient()

  const body = await request.json()

  const {
    company_name,
    contact_name,
    phone,
    email,
    website,
    address,
    city,
    state,
    zip,
    service_type,
    estimated_deal_size,
    employees_count,
    status = 'new',
    priority = 'medium',
    source,
    notes,
    next_follow_up,
    tags,
  } = body

  if (!company_name) {
    return Response.json({ error: 'company_name is required' }, { status: 400 })
  }

  const { data, error } = await supabase
    .from('leads')
    .insert({
      company_name,
      contact_name: contact_name || null,
      phone: phone || null,
      email: email || null,
      website: website || null,
      address: address || null,
      city: city || null,
      state: state || null,
      zip: zip || null,
      service_type: service_type || null,
      estimated_deal_size: estimated_deal_size || null,
      employees_count: employees_count || null,
      status,
      priority,
      source: source || null,
      notes: notes || null,
      next_follow_up: next_follow_up || null,
      tags: tags || null,
    })
    .select()
    .single()

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({ lead: data }, { status: 201 })
}

import { createAdminClient } from '@/lib/supabase/admin'
import { NextRequest } from 'next/server'

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const supabase = createAdminClient()

  const { data: lead, error } = await supabase
    .from('leads')
    .select('*, profiles(id, full_name, role)')
    .eq('id', id)
    .single()

  if (error) {
    return Response.json({ error: error.message }, { status: 404 })
  }

  const { data: callLogs } = await supabase
    .from('call_logs')
    .select('*, profiles(id, full_name, role)')
    .eq('lead_id', id)
    .order('created_at', { ascending: false })

  const { data: onboardingTasks } = await supabase
    .from('onboarding_tasks')
    .select('*')
    .eq('lead_id', id)
    .order('created_at', { ascending: true })

  return Response.json({
    lead,
    callLogs: callLogs || [],
    onboardingTasks: onboardingTasks || [],
  })
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const supabase = createAdminClient()
  const body = await request.json()

  const allowedFields = [
    'company_name', 'contact_name', 'phone', 'email', 'website',
    'address', 'city', 'state', 'zip', 'service_type',
    'estimated_deal_size', 'employees_count', 'status', 'priority',
    'source', 'notes', 'next_follow_up', 'tags', 'assigned_to',
  ]

  const updates: Record<string, unknown> = {}
  for (const field of allowedFields) {
    if (field in body) {
      updates[field] = body[field]
    }
  }

  const { data, error } = await supabase
    .from('leads')
    .update(updates)
    .eq('id', id)
    .select()
    .single()

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({ lead: data })
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const supabase = createAdminClient()

  const { error } = await supabase
    .from('leads')
    .delete()
    .eq('id', id)

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({ success: true })
}

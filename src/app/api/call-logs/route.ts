import { createClient } from '@/lib/supabase/server'
import { NextRequest } from 'next/server'

export async function POST(request: NextRequest) {
  const supabase = await createClient()

  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json()
  const { lead_id, outcome, duration_minutes, notes, next_action, follow_up_date } = body

  if (!lead_id) {
    return Response.json({ error: 'lead_id is required' }, { status: 400 })
  }

  const { data, error } = await supabase
    .from('call_logs')
    .insert({
      lead_id,
      called_by: user.id,
      outcome: outcome || null,
      duration_minutes: duration_minutes || null,
      notes: notes || null,
      next_action: next_action || null,
      follow_up_date: follow_up_date || null,
    })
    .select()
    .single()

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({ callLog: data }, { status: 201 })
}

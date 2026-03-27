import { createClient } from '@/lib/supabase/server'
import { NextRequest } from 'next/server'

export async function POST(request: NextRequest) {
  const supabase = await createClient()

  const body = await request.json()
  const { lead_id, task, due_date } = body

  if (!lead_id || !task) {
    return Response.json({ error: 'lead_id and task are required' }, { status: 400 })
  }

  const { data, error } = await supabase
    .from('onboarding_tasks')
    .insert({
      lead_id,
      task,
      due_date: due_date || null,
    })
    .select()
    .single()

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({ task: data }, { status: 201 })
}

export async function PATCH(request: NextRequest) {
  const supabase = await createClient()

  const { data: { user } } = await supabase.auth.getUser()

  const body = await request.json()
  const { id, completed } = body

  if (!id) {
    return Response.json({ error: 'id is required' }, { status: 400 })
  }

  const updates: Record<string, unknown> = {
    completed: !!completed,
    completed_at: completed ? new Date().toISOString() : null,
    completed_by: completed ? (user?.id || null) : null,
  }

  const { data, error } = await supabase
    .from('onboarding_tasks')
    .update(updates)
    .eq('id', id)
    .select()
    .single()

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({ task: data })
}

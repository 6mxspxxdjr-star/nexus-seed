import { createAdminClient } from '@/lib/supabase/admin'
import { NextRequest } from 'next/server'

const PRIORITY_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 }
const STATUS_ORDER: Record<string, number> = { new: 0, follow_up: 1, contacted: 2 }

export async function GET(request: NextRequest) {
  const supabase = createAdminClient()
  const { searchParams } = new URL(request.url)
  const assignedToParam = searchParams.get('assigned_to')
  const limit = Math.min(parseInt(searchParams.get('limit') || '50'), 200)
  const page = Math.max(1, parseInt(searchParams.get('page') || '1'))
  const offset = (page - 1) * limit

  let query = supabase
    .from('leads')
    .select('*', { count: 'exact' })
    .neq('status', 'dead')
    .neq('status', 'closed_won')
    .neq('status', 'onboarding')
    .neq('status', 'active')

  if (assignedToParam) {
    const { data: profile } = await supabase
      .from('profiles')
      .select('id')
      .ilike('full_name', `%${assignedToParam}%`)
      .maybeSingle()

    if (!profile) {
      return Response.json({ leads: [], total: 0, page, limit })
    }

    query = query.eq('assigned_to', profile.id)
  }

  const { data: leads, error, count } = await query.range(offset, offset + limit - 1)

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  // Sort: priority DESC → status order (new, follow_up, contacted) → next_follow_up ASC
  const sorted = (leads || []).sort((a, b) => {
    const pDiff = (PRIORITY_ORDER[a.priority] ?? 1) - (PRIORITY_ORDER[b.priority] ?? 1)
    if (pDiff !== 0) return pDiff

    const sDiff = (STATUS_ORDER[a.status] ?? 3) - (STATUS_ORDER[b.status] ?? 3)
    if (sDiff !== 0) return sDiff

    if (a.next_follow_up && b.next_follow_up) {
      return new Date(a.next_follow_up).getTime() - new Date(b.next_follow_up).getTime()
    }
    if (a.next_follow_up) return -1
    if (b.next_follow_up) return 1
    return 0
  })

  return Response.json({ leads: sorted, total: count || 0, page, limit })
}

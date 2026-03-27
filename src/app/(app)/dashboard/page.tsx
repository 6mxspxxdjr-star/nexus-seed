import { createClient } from '@/lib/supabase/server'
import DashboardClient from './dashboard-client'

export default async function DashboardPage() {
  const supabase = await createClient()

  const { data: leads } = await supabase
    .from('leads')
    .select('*')
    .order('created_at', { ascending: false })

  const { data: todayCallLogs } = await supabase
    .from('call_logs')
    .select('lead_id')
    .gte('created_at', new Date().toISOString().slice(0, 10))

  const today = new Date()
  today.setHours(23, 59, 59, 999)

  const { data: followUpLeads } = await supabase
    .from('leads')
    .select('id')
    .lte('next_follow_up', today.toISOString())
    .not('next_follow_up', 'is', null)
    .neq('status', 'dead')

  const monthStart = new Date(today.getFullYear(), today.getMonth(), 1).toISOString()
  const { data: closedThisMonth } = await supabase
    .from('leads')
    .select('id')
    .in('status', ['closed_won', 'active'])
    .gte('updated_at', monthStart)

  const stats = {
    totalLeads: leads?.length || 0,
    contactedToday: new Set(todayCallLogs?.map(l => l.lead_id) || []).size,
    followUpsDue: followUpLeads?.length || 0,
    closedThisMonth: closedThisMonth?.length || 0,
  }

  return <DashboardClient leads={leads || []} stats={stats} />
}

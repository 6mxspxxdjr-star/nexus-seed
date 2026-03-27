import { createClient } from '@/lib/supabase/server'
import { notFound } from 'next/navigation'
import LeadDetailClient from './lead-detail-client'

export default async function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const supabase = await createClient()

  const { data: lead } = await supabase
    .from('leads')
    .select('*, profiles(id, full_name, role)')
    .eq('id', id)
    .single()

  if (!lead) {
    notFound()
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

  return (
    <LeadDetailClient
      initialLead={lead}
      initialCallLogs={callLogs || []}
      initialOnboardingTasks={onboardingTasks || []}
    />
  )
}

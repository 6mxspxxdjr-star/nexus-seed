import { createClient } from '@/lib/supabase/server'
import LeadsClient from './leads-client'

export default async function LeadsPage() {
  const supabase = await createClient()

  const { data: leads } = await supabase
    .from('leads')
    .select('*, profiles(id, full_name, role)')
    .order('created_at', { ascending: false })

  return <LeadsClient leads={leads || []} />
}

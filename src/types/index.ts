export type LeadStatus = 'new' | 'contacted' | 'follow_up' | 'quoted' | 'closed_won' | 'onboarding' | 'active' | 'dead'
export type LeadPriority = 'low' | 'medium' | 'high'
export type CallOutcome = 'answered' | 'voicemail' | 'no_answer' | 'callback_scheduled' | 'not_interested' | 'interested' | 'quoted' | 'closed'

export interface Lead {
  id: string
  created_at: string
  updated_at: string
  company_name: string
  contact_name: string | null
  phone: string | null
  email: string | null
  website: string | null
  address: string | null
  city: string | null
  state: string | null
  zip: string | null
  service_type: string | null
  estimated_deal_size: number | null
  employees_count: string | null
  status: LeadStatus
  priority: LeadPriority
  assigned_to: string | null
  next_follow_up: string | null
  source: string | null
  notes: string | null
  tags: string[] | null
  profiles?: Profile | null
}

export interface CallLog {
  id: string
  created_at: string
  lead_id: string
  called_by: string | null
  outcome: CallOutcome | null
  duration_minutes: number | null
  notes: string | null
  next_action: string | null
  follow_up_date: string | null
  profiles?: Profile | null
}

export interface OnboardingTask {
  id: string
  created_at: string
  lead_id: string
  task: string
  completed: boolean
  completed_at: string | null
  completed_by: string | null
  due_date: string | null
  notes: string | null
}

export interface Profile {
  id: string
  full_name: string | null
  role: string | null
}

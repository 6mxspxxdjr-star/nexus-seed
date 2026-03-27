import { createClient } from '@/lib/supabase/server'
import { NextRequest } from 'next/server'

const VALID_FIELDS = [
  'company_name', 'contact_name', 'phone', 'email', 'website',
  'address', 'city', 'state', 'zip', 'service_type',
  'estimated_deal_size', 'employees_count', 'source', 'notes',
]

export async function POST(request: NextRequest) {
  const supabase = await createClient()

  const body = await request.json()
  const { leads } = body

  if (!Array.isArray(leads) || leads.length === 0) {
    return Response.json({ error: 'leads array is required' }, { status: 400 })
  }

  // Sanitize each lead to only include valid fields
  const sanitized = leads
    .filter(l => l.company_name)
    .map(lead => {
      const clean: Record<string, unknown> = {
        status: 'new',
        priority: 'medium',
        source: lead.source || 'csv_import',
      }
      for (const field of VALID_FIELDS) {
        if (field in lead && lead[field] !== undefined && lead[field] !== '') {
          clean[field] = lead[field]
        }
      }
      return clean
    })

  if (sanitized.length === 0) {
    return Response.json({ error: 'No valid leads with company_name' }, { status: 400 })
  }

  const { data, error } = await supabase
    .from('leads')
    .insert(sanitized)
    .select('id')

  if (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }

  return Response.json({ success: true, count: data?.length || 0 })
}

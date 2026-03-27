import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'
import { writeFile } from 'fs/promises'
import path from 'path'

export async function POST() {
  const supabase = await createClient()
  const { data: leads, error } = await supabase.from('leads').select('*')

  if (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 })
  }

  const syncPath = process.env.WORKSPACE_SYNC_PATH || path.join(process.cwd(), 'workspace-leads.json')
  await writeFile(syncPath, JSON.stringify(leads, null, 2))

  return NextResponse.json({ success: true, count: leads.length })
}

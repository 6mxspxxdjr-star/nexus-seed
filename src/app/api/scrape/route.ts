import { createAdminClient } from '@/lib/supabase/admin'
import { ingestGoplacesLeads } from '@/lib/ingest-leads'
import { NextRequest } from 'next/server'
import { exec } from 'child_process'
import { promisify } from 'util'

const execAsync = promisify(exec)

async function postToDiscordScraping(message: string): Promise<void> {
  const webhookUrl = process.env.DISCORD_WEBHOOK_URL_SCRAPING
  if (!webhookUrl) return
  try {
    await fetch(webhookUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: message, username: 'LeadFlow Scraper' }),
    })
  } catch (err) {
    console.error('Discord scraping webhook error:', err)
  }
}

export async function POST(request: NextRequest) {
  const authHeader = request.headers.get('authorization')
  const secret = process.env.DISCORD_INGEST_SECRET

  if (!secret || authHeader !== `Bearer ${secret}`) {
    return Response.json({ error: 'Unauthorized' }, { status: 401 })
  }

  const body = await request.json() as { query?: string; location?: string; limit?: number }
  const { query, location, limit = 20 } = body

  if (!query || !location) {
    return Response.json({ error: 'query and location are required' }, { status: 400 })
  }

  // Sanitize inputs to prevent command injection
  const safeQuery = query.replace(/["`$\\]/g, '')
  const safeLocation = location.replace(/["`$\\]/g, '')
  const safeLimit = Math.min(Math.max(1, Number(limit) || 20), 100)

  let stdout: string
  try {
    const result = await execAsync(
      `goplaces search "${safeQuery} in ${safeLocation}" --json --limit ${safeLimit}`,
      { timeout: 60_000 }
    )
    stdout = result.stdout
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err)
    console.error('goplaces error:', msg)
    return Response.json({ error: 'goplaces command failed', detail: msg }, { status: 500 })
  }

  let places: unknown[]
  try {
    const parsed = JSON.parse(stdout)
    places = Array.isArray(parsed) ? parsed : parsed.places ?? []
  } catch {
    return Response.json({ error: 'Failed to parse goplaces output' }, { status: 500 })
  }

  const supabase = createAdminClient()
  const { inserted, duplicates, skipped_inactive } = await ingestGoplacesLeads(
    places as Parameters<typeof ingestGoplacesLeads>[0],
    supabase
  )
  const total = places.length

  await postToDiscordScraping(
    `🔍 **"${safeQuery} in ${safeLocation}"** — ${total} found → **${inserted} new**, ${duplicates} dupes, ${skipped_inactive} inactive`
  )

  return Response.json({ inserted, duplicates, skipped_inactive, total })
}

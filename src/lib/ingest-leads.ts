import type { SupabaseClient } from '@supabase/supabase-js'

export interface GoplacesPlace {
  name: string
  formattedAddress?: string
  nationalPhoneNumber?: string
  websiteUri?: string
  businessStatus?: string
}

export interface IngestResult {
  inserted: number
  duplicates: number
  skipped_inactive: number
  leads: unknown[]
}

export function parseAddress(formattedAddress: string): {
  address: string | null
  city: string | null
  state: string | null
  zip: string | null
} {
  // Expected: "123 Main St, City, ST 12345, USA"
  const parts = formattedAddress.split(', ')
  let remaining = [...parts]

  // Drop trailing country token (e.g. "USA", "US")
  const last = remaining[remaining.length - 1]
  if (last === 'USA' || last === 'US' || last === 'United States' || /^[A-Z]{2,3}$/.test(last)) {
    remaining = remaining.slice(0, -1)
  }

  if (remaining.length < 2) {
    return { address: formattedAddress, city: null, state: null, zip: null }
  }

  const stateZipPart = remaining[remaining.length - 1]
  const stateZipMatch = stateZipPart.match(/^([A-Z]{2})\s+(\d{5}(?:-\d{4})?)$/)

  if (stateZipMatch) {
    return {
      state: stateZipMatch[1],
      zip: stateZipMatch[2],
      city: remaining[remaining.length - 2],
      address: remaining.length > 2 ? remaining.slice(0, remaining.length - 2).join(', ') : null,
    }
  }

  // State only, no zip
  const stateOnlyMatch = stateZipPart.match(/^([A-Z]{2})$/)
  if (stateOnlyMatch) {
    return {
      state: stateOnlyMatch[1],
      zip: null,
      city: remaining[remaining.length - 2],
      address: remaining.length > 2 ? remaining.slice(0, remaining.length - 2).join(', ') : null,
    }
  }

  return { address: formattedAddress, city: null, state: null, zip: null }
}

export async function ingestGoplacesLeads(
  places: GoplacesPlace[],
  supabase: SupabaseClient
): Promise<IngestResult> {
  let inserted = 0
  let duplicates = 0
  let skipped_inactive = 0
  const insertedLeads: unknown[] = []

  for (const place of places) {
    if (!place.name) continue

    if (place.businessStatus && place.businessStatus !== 'OPERATIONAL') {
      skipped_inactive++
      continue
    }

    const phone = place.nationalPhoneNumber || null
    const { address, city, state, zip } = parseAddress(place.formattedAddress || '')

    // Deduplicate: phone first, then company_name+city
    let isDuplicate = false

    if (phone) {
      const { data: phoneMatch } = await supabase
        .from('leads')
        .select('id')
        .eq('phone', phone)
        .maybeSingle()
      if (phoneMatch) isDuplicate = true
    }

    if (!isDuplicate && city) {
      const { data: nameCityMatch } = await supabase
        .from('leads')
        .select('id')
        .eq('company_name', place.name)
        .eq('city', city)
        .maybeSingle()
      if (nameCityMatch) isDuplicate = true
    }

    if (isDuplicate) {
      duplicates++
      continue
    }

    const { data, error } = await supabase
      .from('leads')
      .insert({
        company_name: place.name,
        phone,
        website: place.websiteUri || null,
        address,
        city,
        state,
        zip,
        source: 'goplaces',
        status: 'new',
        priority: 'medium',
      })
      .select()
      .single()

    if (error) {
      console.error(`Failed to insert lead ${place.name}:`, error.message)
      continue
    }

    inserted++
    insertedLeads.push(data)
  }

  return { inserted, duplicates, skipped_inactive, leads: insertedLeads }
}

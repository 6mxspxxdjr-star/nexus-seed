import { createClient } from '@/lib/supabase/server'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url)
  const code = searchParams.get('code')
  const token_hash = searchParams.get('token_hash')
  const type = searchParams.get('type')
  const error = searchParams.get('error')
  const error_description = searchParams.get('error_description')

  // Use NEXT_PUBLIC_SITE_URL if available, otherwise use request origin
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || origin

  // Handle errors from Supabase
  if (error) {
    console.error('Auth callback error:', error, error_description)
    return NextResponse.redirect(`${siteUrl}/login?error=${encodeURIComponent(error_description || error)}`)
  }

  const supabase = await createClient()

  // Handle PKCE flow (code exchange)
  if (code) {
    const { error: exchangeError } = await supabase.auth.exchangeCodeForSession(code)
    if (!exchangeError) {
      return NextResponse.redirect(`${siteUrl}/dashboard`)
    }
    console.error('Code exchange error:', exchangeError)
    return NextResponse.redirect(`${siteUrl}/login?error=${encodeURIComponent(exchangeError.message)}`)
  }

  // Handle OTP/magic link flow (token_hash)
  if (token_hash && type) {
    const { error: verifyError } = await supabase.auth.verifyOtp({ token_hash, type: type as 'email' | 'magiclink' })
    if (!verifyError) {
      return NextResponse.redirect(`${siteUrl}/dashboard`)
    }
    console.error('OTP verify error:', verifyError)
    return NextResponse.redirect(`${siteUrl}/login?error=${encodeURIComponent(verifyError.message)}`)
  }

  // Fallback
  return NextResponse.redirect(`${siteUrl}/dashboard`)
}

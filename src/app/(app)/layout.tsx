import { redirect } from 'next/navigation'
import { createClient } from '@/lib/supabase/server'
import NavClient from '@/components/nav-client'

export default async function AppLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const supabase = await createClient()
  const { data: { user } } = await supabase.auth.getUser()

  if (!user) {
    redirect('/login')
  }

  const { data: profile } = await supabase
    .from('profiles')
    .select('*')
    .eq('id', user.id)
    .single()

  return (
    <div className="min-h-screen bg-gray-950">
      <NavClient user={user} profile={profile} />
      <main className="pt-16">
        {children}
      </main>
    </div>
  )
}

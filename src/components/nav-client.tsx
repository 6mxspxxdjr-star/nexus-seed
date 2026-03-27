'use client'

import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { Wind, LayoutDashboard, Users, Upload, LogOut, ChevronDown } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import type { User } from '@supabase/supabase-js'
import type { Profile } from '@/types'

interface NavClientProps {
  user: User
  profile: Profile | null
}

export default function NavClient({ user, profile }: NavClientProps) {
  const pathname = usePathname()
  const router = useRouter()
  const supabase = createClient()

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    router.push('/login')
    router.refresh()
  }

  const initials = profile?.full_name
    ? profile.full_name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : user.email?.slice(0, 2).toUpperCase() || 'U'

  const displayName = profile?.full_name || user.email || 'User'

  const navLinks = [
    { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { href: '/leads', label: 'Leads', icon: Users },
    { href: '/import', label: 'Import', icon: Upload },
  ]

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 h-16 bg-gray-900 border-b border-gray-800 flex items-center px-6">
      <div className="flex items-center gap-2 mr-8">
        <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
          <Wind className="w-5 h-5 text-white" />
        </div>
        <span className="text-lg font-bold text-white tracking-tight">LeadFlow</span>
      </div>

      <div className="flex items-center gap-1 flex-1">
        {navLinks.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={`flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
              pathname === href || pathname.startsWith(href + '/')
                ? 'bg-gray-800 text-white'
                : 'text-gray-400 hover:text-white hover:bg-gray-800'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </Link>
        ))}
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger className="flex items-center gap-2 px-2 py-1.5 rounded-md hover:bg-gray-800 transition-colors outline-none">
          <Avatar className="h-8 w-8">
            <AvatarFallback className="bg-indigo-600 text-white text-xs font-semibold">
              {initials}
            </AvatarFallback>
          </Avatar>
          <span className="text-sm text-gray-300 hidden sm:block">{displayName}</span>
          <ChevronDown className="w-3 h-3 text-gray-500" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-48 bg-gray-900 border-gray-800">
          <DropdownMenuLabel className="text-gray-400 text-xs">{user.email}</DropdownMenuLabel>
          <DropdownMenuSeparator className="bg-gray-800" />
          <DropdownMenuItem
            onClick={handleSignOut}
            className="text-gray-300 hover:text-white hover:bg-gray-800 cursor-pointer"
          >
            <LogOut className="w-4 h-4 mr-2" />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </nav>
  )
}

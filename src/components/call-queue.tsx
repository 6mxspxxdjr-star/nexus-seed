'use client'

import { useState, useEffect, useCallback } from 'react'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { StatusBadge } from '@/components/status-badge'
import CallLogModal from '@/components/call-log-modal'
import { Phone, Copy, ChevronRight, User, Users } from 'lucide-react'
import { toast } from 'sonner'
import type { Lead, CallLog } from '@/types'

function isOverdue(lead: Lead): boolean {
  return !!lead.next_follow_up && new Date(lead.next_follow_up) < new Date()
}

function cardBorderClass(lead: Lead): string {
  if (lead.priority === 'high') return 'border-l-4 border-l-red-500'
  if (isOverdue(lead)) return 'border-l-4 border-l-yellow-500'
  return 'border-l-4 border-l-gray-800'
}

function FilterBtn({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
        active
          ? 'bg-indigo-600 text-white'
          : 'bg-gray-800 text-gray-400 hover:bg-gray-700 hover:text-gray-200'
      }`}
    >
      {children}
    </button>
  )
}

export default function CallQueue() {
  const [leads, setLeads] = useState<Lead[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<'mine' | 'all'>('mine')
  const [myName, setMyName] = useState<string | null>(null)
  const [callModalOpen, setCallModalOpen] = useState(false)

  useEffect(() => {
    const supabase = createClient()
    supabase.auth.getUser().then(async ({ data: { user } }) => {
      if (!user) return
      const { data: profile } = await supabase
        .from('profiles')
        .select('full_name')
        .eq('id', user.id)
        .maybeSingle()
      setMyName(profile?.full_name ?? null)
    })
  }, [])

  const fetchQueue = useCallback(async () => {
    setLoading(true)
    const params = new URLSearchParams({ limit: '100' })
    if (filter === 'mine' && myName) {
      params.set('assigned_to', myName)
    }
    try {
      const res = await fetch(`/api/call-queue?${params}`)
      const data = await res.json()
      setLeads(data.leads || [])
    } catch {
      toast.error('Failed to load call queue')
    } finally {
      setLoading(false)
    }
    setCurrentIndex(0)
  }, [filter, myName])

  useEffect(() => {
    fetchQueue()
  }, [fetchQueue])

  const currentLead = leads[currentIndex]

  const copyPhone = async (phone: string) => {
    await navigator.clipboard.writeText(phone)
    toast.success('Copied!')
  }

  const handleCallSaved = (_log: CallLog) => {
    if (currentIndex < leads.length - 1) {
      setCurrentIndex(i => i + 1)
    } else {
      fetchQueue()
    }
  }

  const header = (
    <div className="flex items-center justify-between mb-4">
      <div className="flex gap-2">
        <FilterBtn active={filter === 'mine'} onClick={() => setFilter('mine')}>
          <User className="w-3.5 h-3.5" />
          My Queue
        </FilterBtn>
        <FilterBtn active={filter === 'all'} onClick={() => setFilter('all')}>
          <Users className="w-3.5 h-3.5" />
          All
        </FilterBtn>
      </div>
      {leads.length > 0 && (
        <span className="text-sm text-gray-400 font-mono tabular-nums">
          Lead {currentIndex + 1} of {leads.length}
        </span>
      )}
    </div>
  )

  if (loading) {
    return (
      <div className="p-4 max-w-2xl mx-auto">
        {header}
        <div className="text-center py-16 text-gray-500">Loading queue...</div>
      </div>
    )
  }

  if (leads.length === 0) {
    return (
      <div className="p-4 max-w-2xl mx-auto">
        {header}
        <div className="text-center py-16 text-gray-500">
          <Phone className="w-8 h-8 mx-auto mb-3 opacity-30" />
          <p className="text-sm">No leads in queue</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-4 max-w-2xl mx-auto space-y-4">
      {header}

      {/* Current lead card */}
      {currentLead && (
        <div className={`bg-gray-900 rounded-xl p-5 space-y-4 ${cardBorderClass(currentLead)}`}>
          {/* Company + location */}
          <div>
            <h2 className="text-xl font-bold text-white leading-tight">
              {currentLead.company_name}
            </h2>
            {(currentLead.city || currentLead.state) && (
              <p className="text-gray-400 text-sm mt-0.5">
                {[currentLead.city, currentLead.state].filter(Boolean).join(', ')}
              </p>
            )}
          </div>

          {/* Phone — extra large, monospace, tap to copy */}
          {currentLead.phone ? (
            <button
              onClick={() => copyPhone(currentLead.phone!)}
              className="flex items-center gap-3 w-full text-left group"
            >
              <Phone className="w-5 h-5 text-green-400 shrink-0" />
              <span className="text-3xl font-bold font-mono text-green-400 tracking-wide group-hover:text-green-300 transition-colors">
                {currentLead.phone}
              </span>
              <Copy className="w-4 h-4 text-gray-500 group-hover:text-gray-300 transition-colors ml-auto shrink-0" />
            </button>
          ) : (
            <p className="text-gray-500 italic text-sm">No phone on file</p>
          )}

          {/* Contact name */}
          {currentLead.contact_name && (
            <p className="text-gray-300 text-sm">
              Contact: <span className="text-white font-medium">{currentLead.contact_name}</span>
            </p>
          )}

          {/* Badges */}
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={currentLead.status} />
            {currentLead.priority === 'high' && (
              <Badge variant="outline" className="bg-red-900/50 text-red-300 border-red-800 text-xs">
                High Priority
              </Badge>
            )}
            {isOverdue(currentLead) && (
              <Badge variant="outline" className="bg-yellow-900/50 text-yellow-300 border-yellow-800 text-xs">
                Follow-up Overdue
              </Badge>
            )}
          </div>

          {currentLead.next_follow_up && (
            <p className="text-xs text-gray-500">
              Follow-up: {new Date(currentLead.next_follow_up).toLocaleDateString()}
            </p>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-1">
            <Button
              onClick={() => setCallModalOpen(true)}
              className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold h-14 text-base"
            >
              <Phone className="w-4 h-4 mr-2" />
              Log Call
            </Button>
            {currentIndex < leads.length - 1 && (
              <Button
                variant="outline"
                onClick={() => setCurrentIndex(i => i + 1)}
                className="border-gray-700 text-gray-300 hover:bg-gray-800 px-4"
                title="Skip to next lead"
              >
                <ChevronRight className="w-5 h-5" />
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Up-next preview */}
      {leads.slice(currentIndex + 1, currentIndex + 4).length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-500 uppercase tracking-wider px-1">Up Next</p>
          {leads.slice(currentIndex + 1, currentIndex + 4).map((lead, i) => (
            <button
              key={lead.id}
              onClick={() => setCurrentIndex(currentIndex + 1 + i)}
              className="w-full flex items-center gap-3 bg-gray-900/60 hover:bg-gray-900 rounded-lg px-4 py-3 text-left transition-colors"
            >
              <span className="text-gray-500 text-xs font-mono w-5 shrink-0">
                {currentIndex + 2 + i}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-200 truncate font-medium">{lead.company_name}</p>
                {lead.phone && (
                  <p className="text-xs text-gray-500 font-mono">{lead.phone}</p>
                )}
              </div>
              <StatusBadge status={lead.status} />
            </button>
          ))}
        </div>
      )}

      {currentLead && (
        <CallLogModal
          leadId={currentLead.id}
          open={callModalOpen}
          onOpenChange={setCallModalOpen}
          onSaved={handleCallSaved}
        />
      )}
    </div>
  )
}

'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { format, parseISO } from 'date-fns'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { StatusBadge, PriorityBadge } from '@/components/status-badge'
import LeadForm from '@/components/lead-form'
import { Search, Plus, ExternalLink, Phone } from 'lucide-react'
import type { Lead, LeadStatus, LeadPriority } from '@/types'

interface LeadsClientProps {
  leads: Lead[]
}

export default function LeadsClient({ leads }: LeadsClientProps) {
  const router = useRouter()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<LeadStatus | 'all'>('all')
  const [priorityFilter, setPriorityFilter] = useState<LeadPriority | 'all'>('all')
  const [addLeadOpen, setAddLeadOpen] = useState(false)

  const filtered = leads.filter(lead => {
    const matchesSearch = !search || [
      lead.company_name,
      lead.contact_name,
      lead.phone,
      lead.email,
      lead.city,
    ].some(f => f?.toLowerCase().includes(search.toLowerCase()))

    const matchesStatus = statusFilter === 'all' || lead.status === statusFilter
    const matchesPriority = priorityFilter === 'all' || lead.priority === priorityFilter

    return matchesSearch && matchesStatus && matchesPriority
  })

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Leads</h1>
          <p className="text-gray-400 text-sm mt-0.5">{filtered.length} of {leads.length} leads</p>
        </div>
        <Button
          onClick={() => setAddLeadOpen(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Lead
        </Button>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search company, contact, phone..."
            className="bg-gray-900 border-gray-800 text-white pl-9"
          />
        </div>
        <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as LeadStatus | 'all')}>
          <SelectTrigger className="bg-gray-900 border-gray-800 text-white w-40">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent className="bg-gray-900 border-gray-700">
            <SelectItem value="all" className="text-gray-200 focus:bg-gray-800">All Statuses</SelectItem>
            {(['new', 'contacted', 'follow_up', 'quoted', 'closed_won', 'onboarding', 'active', 'dead'] as LeadStatus[]).map(s => (
              <SelectItem key={s} value={s} className="text-gray-200 focus:bg-gray-800">
                {s.charAt(0).toUpperCase() + s.slice(1).replace('_', ' ')}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={priorityFilter} onValueChange={(v) => setPriorityFilter(v as LeadPriority | 'all')}>
          <SelectTrigger className="bg-gray-900 border-gray-800 text-white w-36">
            <SelectValue placeholder="All priorities" />
          </SelectTrigger>
          <SelectContent className="bg-gray-900 border-gray-700">
            <SelectItem value="all" className="text-gray-200 focus:bg-gray-800">All Priorities</SelectItem>
            <SelectItem value="high" className="text-gray-200 focus:bg-gray-800">High</SelectItem>
            <SelectItem value="medium" className="text-gray-200 focus:bg-gray-800">Medium</SelectItem>
            <SelectItem value="low" className="text-gray-200 focus:bg-gray-800">Low</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow className="border-gray-800 hover:bg-transparent">
              <TableHead className="text-gray-400 font-medium">Company</TableHead>
              <TableHead className="text-gray-400 font-medium">Contact</TableHead>
              <TableHead className="text-gray-400 font-medium">Phone</TableHead>
              <TableHead className="text-gray-400 font-medium">Status</TableHead>
              <TableHead className="text-gray-400 font-medium">Priority</TableHead>
              <TableHead className="text-gray-400 font-medium">Next Follow-up</TableHead>
              <TableHead className="text-gray-400 font-medium">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filtered.length === 0 && (
              <TableRow className="border-gray-800">
                <TableCell colSpan={7} className="text-center py-12 text-gray-500">
                  No leads found
                </TableCell>
              </TableRow>
            )}
            {filtered.map(lead => (
              <TableRow key={lead.id} className="border-gray-800 hover:bg-gray-800/50">
                <TableCell>
                  <Link href={`/leads/${lead.id}`} className="font-medium text-white hover:text-indigo-400 transition-colors">
                    {lead.company_name}
                  </Link>
                  {(lead.city || lead.state) && (
                    <p className="text-xs text-gray-500 mt-0.5">
                      {[lead.city, lead.state].filter(Boolean).join(', ')}
                    </p>
                  )}
                </TableCell>
                <TableCell className="text-gray-300 text-sm">{lead.contact_name || '—'}</TableCell>
                <TableCell>
                  {lead.phone ? (
                    <a href={`tel:${lead.phone}`} className="flex items-center gap-1 text-gray-300 text-sm hover:text-white transition-colors">
                      <Phone className="w-3 h-3" />
                      {lead.phone}
                    </a>
                  ) : (
                    <span className="text-gray-600">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <StatusBadge status={lead.status} />
                </TableCell>
                <TableCell>
                  <PriorityBadge priority={lead.priority} />
                </TableCell>
                <TableCell className="text-sm">
                  {lead.next_follow_up ? (
                    <span className={`${new Date(lead.next_follow_up) < new Date() ? 'text-amber-400' : 'text-gray-300'}`}>
                      {format(parseISO(lead.next_follow_up), 'MMM d, h:mm a')}
                    </span>
                  ) : (
                    <span className="text-gray-600">—</span>
                  )}
                </TableCell>
                <TableCell>
                  <Link href={`/leads/${lead.id}`}>
                    <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white hover:bg-gray-800 h-7 px-2">
                      <ExternalLink className="w-3.5 h-3.5" />
                    </Button>
                  </Link>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <Dialog open={addLeadOpen} onOpenChange={setAddLeadOpen}>
        <DialogContent className="bg-gray-900 border-gray-800 text-white max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="text-white">Add New Lead</DialogTitle>
          </DialogHeader>
          <LeadForm
            onSuccess={() => {
              setAddLeadOpen(false)
              router.refresh()
            }}
            onCancel={() => setAddLeadOpen(false)}
          />
        </DialogContent>
      </Dialog>
    </div>
  )
}

'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Users, Phone, Calendar, TrendingUp, Plus, Kanban } from 'lucide-react'
import LeadCard from '@/components/lead-card'
import LeadForm from '@/components/lead-form'
import CallQueue from '@/components/call-queue'
import type { Lead, LeadStatus } from '@/types'

const KANBAN_COLUMNS: { status: LeadStatus; label: string }[] = [
  { status: 'new', label: 'New' },
  { status: 'contacted', label: 'Contacted' },
  { status: 'follow_up', label: 'Follow Up' },
  { status: 'quoted', label: 'Quoted' },
  { status: 'closed_won', label: 'Closed Won' },
  { status: 'onboarding', label: 'Onboarding' },
  { status: 'active', label: 'Active' },
]

const COLUMN_COLORS: Record<LeadStatus, string> = {
  new: 'text-gray-400',
  contacted: 'text-blue-400',
  follow_up: 'text-amber-400',
  quoted: 'text-purple-400',
  closed_won: 'text-green-400',
  onboarding: 'text-teal-400',
  active: 'text-emerald-400',
  dead: 'text-red-400',
}

interface DashboardClientProps {
  leads: Lead[]
  stats: {
    totalLeads: number
    contactedToday: number
    followUpsDue: number
    closedThisMonth: number
  }
}

export default function DashboardClient({ leads, stats }: DashboardClientProps) {
  const router = useRouter()
  const [addLeadOpen, setAddLeadOpen] = useState(false)

  const grouped = KANBAN_COLUMNS.reduce((acc, col) => {
    acc[col.status] = leads.filter(l => l.status === col.status)
    return acc
  }, {} as Record<LeadStatus, Lead[]>)

  const statCards = [
    { label: 'Total Leads', value: stats.totalLeads, icon: Users, color: 'text-indigo-400' },
    { label: 'Contacted Today', value: stats.contactedToday, icon: Phone, color: 'text-blue-400' },
    { label: 'Follow-ups Due', value: stats.followUpsDue, icon: Calendar, color: 'text-amber-400' },
    { label: 'Closed This Month', value: stats.closedThisMonth, icon: TrendingUp, color: 'text-green-400' },
  ]

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-400 text-sm mt-0.5">Overview of your pipeline</p>
        </div>
        <Button
          onClick={() => setAddLeadOpen(true)}
          className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2"
        >
          <Plus className="w-4 h-4" />
          Add Lead
        </Button>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map(({ label, value, icon: Icon, color }) => (
          <Card key={label} className="bg-gray-900 border-gray-800">
            <CardHeader className="pb-2 pt-4 px-4">
              <CardTitle className="text-gray-400 text-xs font-medium uppercase tracking-wider flex items-center gap-2">
                <Icon className={`w-3.5 h-3.5 ${color}`} />
                {label}
              </CardTitle>
            </CardHeader>
            <CardContent className="pb-4 px-4">
              <p className={`text-3xl font-bold ${color}`}>{value}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Tabs defaultValue="pipeline">
        <TabsList className="bg-gray-900 border border-gray-800">
          <TabsTrigger
            value="pipeline"
            className="data-[state=active]:bg-gray-800 data-[state=active]:text-white text-gray-400 gap-2"
          >
            <Kanban className="w-3.5 h-3.5" />
            Pipeline
          </TabsTrigger>
          <TabsTrigger
            value="call-queue"
            className="data-[state=active]:bg-gray-800 data-[state=active]:text-white text-gray-400 gap-2"
          >
            <Phone className="w-3.5 h-3.5" />
            Call Queue
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pipeline" className="mt-4">
          <div className="flex gap-4 overflow-x-auto pb-4">
            {KANBAN_COLUMNS.map(col => (
              <div key={col.status} className="flex-shrink-0 w-64">
                <div className="flex items-center justify-between mb-2 px-1">
                  <span className={`text-sm font-semibold ${COLUMN_COLORS[col.status]}`}>{col.label}</span>
                  <span className="text-xs text-gray-500 bg-gray-800 px-1.5 py-0.5 rounded font-medium">
                    {grouped[col.status]?.length || 0}
                  </span>
                </div>
                <div className="space-y-2 min-h-[100px]">
                  {(grouped[col.status] || []).map(lead => (
                    <LeadCard key={lead.id} lead={lead} />
                  ))}
                  {(grouped[col.status] || []).length === 0 && (
                    <div className="border border-dashed border-gray-800 rounded-lg p-4 text-center">
                      <p className="text-gray-600 text-xs">No leads</p>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="call-queue" className="mt-4">
          <CallQueue />
        </TabsContent>
      </Tabs>

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

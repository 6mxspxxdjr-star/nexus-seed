'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { format, parseISO } from 'date-fns'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Checkbox } from '@/components/ui/checkbox'
import PipelineStepper from '@/components/pipeline-stepper'
import CallLogModal from '@/components/call-log-modal'
import { StatusBadge, PriorityBadge } from '@/components/status-badge'
import {
  ArrowLeft, Phone, Mail, Globe, MapPin, Building2, Edit3, Save, X,
  Plus, Trash2, Clock, User, Calendar
} from 'lucide-react'
import { toast } from 'sonner'
import type { Lead, CallLog, OnboardingTask, LeadStatus, LeadPriority } from '@/types'

interface LeadDetailClientProps {
  initialLead: Lead
  initialCallLogs: CallLog[]
  initialOnboardingTasks: OnboardingTask[]
}

const OUTCOME_LABELS: Record<string, string> = {
  answered: 'Answered',
  voicemail: 'Voicemail',
  no_answer: 'No Answer',
  callback_scheduled: 'Callback Scheduled',
  not_interested: 'Not Interested',
  interested: 'Interested',
  quoted: 'Quoted',
  closed: 'Closed',
}

const OUTCOME_COLORS: Record<string, string> = {
  answered: 'text-green-400',
  voicemail: 'text-yellow-400',
  no_answer: 'text-gray-400',
  callback_scheduled: 'text-blue-400',
  not_interested: 'text-red-400',
  interested: 'text-emerald-400',
  quoted: 'text-purple-400',
  closed: 'text-teal-400',
}

export default function LeadDetailClient({
  initialLead,
  initialCallLogs,
  initialOnboardingTasks,
}: LeadDetailClientProps) {
  const router = useRouter()
  const supabase = createClient()
  const [lead, setLead] = useState<Lead>(initialLead)
  const [callLogs, setCallLogs] = useState<CallLog[]>(initialCallLogs)
  const [onboardingTasks, setOnboardingTasks] = useState<OnboardingTask[]>(initialOnboardingTasks)
  const [editing, setEditing] = useState(false)
  const [callLogOpen, setCallLogOpen] = useState(false)
  const [newTaskText, setNewTaskText] = useState('')
  const [saving, setSaving] = useState(false)
  const [editData, setEditData] = useState({
    company_name: lead.company_name,
    contact_name: lead.contact_name || '',
    phone: lead.phone || '',
    email: lead.email || '',
    website: lead.website || '',
    address: lead.address || '',
    city: lead.city || '',
    state: lead.state || '',
    zip: lead.zip || '',
    service_type: lead.service_type || '',
    estimated_deal_size: lead.estimated_deal_size?.toString() || '',
    employees_count: lead.employees_count || '',
    source: lead.source || '',
    priority: lead.priority,
    next_follow_up: lead.next_follow_up ? lead.next_follow_up.slice(0, 16) : '',
    notes: lead.notes || '',
  })

  const handleSave = async () => {
    setSaving(true)
    const payload = {
      company_name: editData.company_name,
      contact_name: editData.contact_name || null,
      phone: editData.phone || null,
      email: editData.email || null,
      website: editData.website || null,
      address: editData.address || null,
      city: editData.city || null,
      state: editData.state || null,
      zip: editData.zip || null,
      service_type: editData.service_type || null,
      estimated_deal_size: editData.estimated_deal_size ? parseFloat(editData.estimated_deal_size) : null,
      employees_count: editData.employees_count || null,
      source: editData.source || null,
      priority: editData.priority,
      next_follow_up: editData.next_follow_up || null,
      notes: editData.notes || null,
    }

    const { data, error } = await supabase
      .from('leads')
      .update(payload)
      .eq('id', lead.id)
      .select()
      .single()

    setSaving(false)

    if (error) {
      toast.error(error.message)
      return
    }

    setLead(prev => ({ ...prev, ...data }))
    setEditing(false)
    toast.success('Lead updated!')
  }

  const handleStatusChange = (status: LeadStatus) => {
    setLead(prev => ({ ...prev, status }))
  }

  const handleAddTask = async () => {
    if (!newTaskText.trim()) return
    const { data, error } = await supabase
      .from('onboarding_tasks')
      .insert({ lead_id: lead.id, task: newTaskText.trim() })
      .select()
      .single()

    if (error) {
      toast.error(error.message)
      return
    }

    setOnboardingTasks(prev => [...prev, data as OnboardingTask])
    setNewTaskText('')
  }

  const handleToggleTask = async (task: OnboardingTask) => {
    const { data: { user } } = await supabase.auth.getUser()
    const updates: Partial<OnboardingTask> = {
      completed: !task.completed,
      completed_at: !task.completed ? new Date().toISOString() : null,
      completed_by: !task.completed ? (user?.id ?? null) : null,
    }

    const { error } = await supabase
      .from('onboarding_tasks')
      .update(updates)
      .eq('id', task.id)

    if (error) {
      toast.error(error.message)
      return
    }

    setOnboardingTasks(prev =>
      prev.map(t => t.id === task.id ? { ...t, ...updates } : t)
    )
  }

  const handleDeleteTask = async (taskId: string) => {
    const { error } = await supabase
      .from('onboarding_tasks')
      .delete()
      .eq('id', taskId)

    if (error) {
      toast.error(error.message)
      return
    }

    setOnboardingTasks(prev => prev.filter(t => t.id !== taskId))
  }

  const handleDeleteLead = async () => {
    if (!confirm('Are you sure you want to delete this lead? This cannot be undone.')) return

    const { error } = await supabase.from('leads').delete().eq('id', lead.id)
    if (error) {
      toast.error(error.message)
      return
    }

    toast.success('Lead deleted')
    router.push('/leads')
    router.refresh()
  }

  const completedTasks = onboardingTasks.filter(t => t.completed).length
  const progress = onboardingTasks.length > 0 ? Math.round((completedTasks / onboardingTasks.length) * 100) : 0

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      <div className="flex items-center gap-4">
        <Link href="/leads">
          <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white hover:bg-gray-800 gap-1.5">
            <ArrowLeft className="w-4 h-4" />
            Leads
          </Button>
        </Link>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">{lead.company_name}</h1>
            <StatusBadge status={lead.status} />
            <PriorityBadge priority={lead.priority} />
          </div>
          {(lead.city || lead.state) && (
            <p className="text-gray-400 text-sm flex items-center gap-1 mt-0.5">
              <MapPin className="w-3 h-3" />
              {[lead.city, lead.state].filter(Boolean).join(', ')}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => setCallLogOpen(true)}
            className="bg-green-700 hover:bg-green-600 text-white gap-2"
          >
            <Phone className="w-4 h-4" />
            Log Call
          </Button>
          <Button
            variant="outline"
            onClick={handleDeleteLead}
            className="border-red-900 text-red-400 hover:bg-red-950 hover:text-red-300"
          >
            <Trash2 className="w-4 h-4" />
          </Button>
        </div>
      </div>

      <PipelineStepper
        leadId={lead.id}
        currentStatus={lead.status}
        onStatusChange={handleStatusChange}
      />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        {/* Left: Lead Info */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Lead Info</h2>
              {!editing ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setEditing(true)}
                  className="text-gray-400 hover:text-white hover:bg-gray-800 h-7 px-2 gap-1"
                >
                  <Edit3 className="w-3.5 h-3.5" />
                  Edit
                </Button>
              ) : (
                <div className="flex gap-1">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setEditing(false)}
                    className="text-gray-400 hover:text-white hover:bg-gray-800 h-7 px-2"
                  >
                    <X className="w-3.5 h-3.5" />
                  </Button>
                  <Button
                    size="sm"
                    onClick={handleSave}
                    disabled={saving}
                    className="bg-indigo-600 hover:bg-indigo-700 text-white h-7 px-2 gap-1"
                  >
                    <Save className="w-3.5 h-3.5" />
                    {saving ? 'Saving...' : 'Save'}
                  </Button>
                </div>
              )}
            </div>

            {editing ? (
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Company Name</Label>
                  <Input
                    value={editData.company_name}
                    onChange={e => setEditData(p => ({ ...p, company_name: e.target.value }))}
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Contact Name</Label>
                  <Input
                    value={editData.contact_name}
                    onChange={e => setEditData(p => ({ ...p, contact_name: e.target.value }))}
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Phone</Label>
                  <Input
                    value={editData.phone}
                    onChange={e => setEditData(p => ({ ...p, phone: e.target.value }))}
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Email</Label>
                  <Input
                    type="email"
                    value={editData.email}
                    onChange={e => setEditData(p => ({ ...p, email: e.target.value }))}
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Website</Label>
                  <Input
                    value={editData.website}
                    onChange={e => setEditData(p => ({ ...p, website: e.target.value }))}
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">City</Label>
                  <Input
                    value={editData.city}
                    onChange={e => setEditData(p => ({ ...p, city: e.target.value }))}
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label className="text-gray-400 text-xs">State</Label>
                    <Input
                      value={editData.state}
                      onChange={e => setEditData(p => ({ ...p, state: e.target.value }))}
                      className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                      maxLength={2}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-gray-400 text-xs">Zip</Label>
                    <Input
                      value={editData.zip}
                      onChange={e => setEditData(p => ({ ...p, zip: e.target.value }))}
                      className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Priority</Label>
                  <Select value={editData.priority} onValueChange={v => setEditData(p => ({ ...p, priority: v as LeadPriority }))}>
                    <SelectTrigger className="bg-gray-800 border-gray-700 text-white h-8 text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-gray-900 border-gray-700">
                      <SelectItem value="low" className="text-gray-200 focus:bg-gray-800">Low</SelectItem>
                      <SelectItem value="medium" className="text-gray-200 focus:bg-gray-800">Medium</SelectItem>
                      <SelectItem value="high" className="text-gray-200 focus:bg-gray-800">High</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Next Follow-up</Label>
                  <Input
                    type="datetime-local"
                    value={editData.next_follow_up}
                    onChange={e => setEditData(p => ({ ...p, next_follow_up: e.target.value }))}
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Est. Deal Size ($)</Label>
                  <Input
                    type="number"
                    value={editData.estimated_deal_size}
                    onChange={e => setEditData(p => ({ ...p, estimated_deal_size: e.target.value }))}
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-gray-400 text-xs">Source</Label>
                  <Input
                    value={editData.source}
                    onChange={e => setEditData(p => ({ ...p, source: e.target.value }))}
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm"
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {lead.contact_name && (
                  <div className="flex items-center gap-2">
                    <User className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <span className="text-sm text-gray-300">{lead.contact_name}</span>
                  </div>
                )}
                {lead.phone && (
                  <div className="flex items-center gap-2">
                    <Phone className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <a href={`tel:${lead.phone}`} className="text-sm text-gray-300 hover:text-white transition-colors">
                      {lead.phone}
                    </a>
                  </div>
                )}
                {lead.email && (
                  <div className="flex items-center gap-2">
                    <Mail className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <a href={`mailto:${lead.email}`} className="text-sm text-gray-300 hover:text-white transition-colors truncate">
                      {lead.email}
                    </a>
                  </div>
                )}
                {lead.website && (
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <a href={lead.website.startsWith('http') ? lead.website : `https://${lead.website}`}
                      target="_blank" rel="noopener noreferrer"
                      className="text-sm text-indigo-400 hover:text-indigo-300 transition-colors truncate">
                      {lead.website}
                    </a>
                  </div>
                )}
                {(lead.address || lead.city) && (
                  <div className="flex items-start gap-2">
                    <MapPin className="w-4 h-4 text-gray-500 flex-shrink-0 mt-0.5" />
                    <span className="text-sm text-gray-300">
                      {[lead.address, lead.city, lead.state, lead.zip].filter(Boolean).join(', ')}
                    </span>
                  </div>
                )}
                {lead.service_type && (
                  <div className="flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-gray-500 flex-shrink-0" />
                    <span className="text-sm text-gray-300">{lead.service_type}</span>
                  </div>
                )}
                {lead.estimated_deal_size && (
                  <div className="pt-1">
                    <Badge variant="outline" className="border-green-800 text-green-400 bg-green-900/20 text-xs">
                      ${lead.estimated_deal_size.toLocaleString()} est. value
                    </Badge>
                  </div>
                )}
                {lead.next_follow_up && (
                  <div className="flex items-center gap-2">
                    <Calendar className="w-4 h-4 text-amber-500 flex-shrink-0" />
                    <span className="text-sm text-amber-400">
                      Follow up: {format(parseISO(lead.next_follow_up), 'MMM d, h:mm a')}
                    </span>
                  </div>
                )}
                {lead.source && (
                  <div className="text-xs text-gray-500">Source: {lead.source}</div>
                )}
                <div className="text-xs text-gray-600 pt-1">
                  Added {format(parseISO(lead.created_at), 'MMM d, yyyy')}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right: Tabs */}
        <div className="lg:col-span-3">
          <Tabs defaultValue="calls">
            <TabsList className="bg-gray-900 border border-gray-800 mb-4">
              <TabsTrigger value="calls" className="data-[state=active]:bg-gray-800 data-[state=active]:text-white text-gray-400">
                Call Log ({callLogs.length})
              </TabsTrigger>
              <TabsTrigger value="onboarding" className="data-[state=active]:bg-gray-800 data-[state=active]:text-white text-gray-400">
                Onboarding ({progress}%)
              </TabsTrigger>
              <TabsTrigger value="notes" className="data-[state=active]:bg-gray-800 data-[state=active]:text-white text-gray-400">
                Notes
              </TabsTrigger>
            </TabsList>

            <TabsContent value="calls" className="space-y-3">
              <div className="flex justify-end">
                <Button
                  onClick={() => setCallLogOpen(true)}
                  size="sm"
                  className="bg-indigo-600 hover:bg-indigo-700 text-white gap-1.5"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Log Call
                </Button>
              </div>
              {callLogs.length === 0 ? (
                <div className="bg-gray-900 border border-gray-800 rounded-lg p-8 text-center">
                  <Phone className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                  <p className="text-gray-500 text-sm">No calls logged yet</p>
                </div>
              ) : (
                callLogs.map(log => (
                  <div key={log.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                    <div className="flex items-start justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className={`font-medium text-sm ${log.outcome ? OUTCOME_COLORS[log.outcome] : 'text-gray-400'}`}>
                          {log.outcome ? OUTCOME_LABELS[log.outcome] : 'Call'}
                        </span>
                        {log.duration_minutes && (
                          <div className="flex items-center gap-1 text-xs text-gray-500">
                            <Clock className="w-3 h-3" />
                            {log.duration_minutes}m
                          </div>
                        )}
                      </div>
                      <span className="text-xs text-gray-500">
                        {format(parseISO(log.created_at), 'MMM d, h:mm a')}
                      </span>
                    </div>
                    {log.notes && <p className="text-sm text-gray-300 mb-2">{log.notes}</p>}
                    {log.next_action && (
                      <p className="text-xs text-indigo-400">Next: {log.next_action}</p>
                    )}
                    {log.follow_up_date && (
                      <p className="text-xs text-amber-400 flex items-center gap-1 mt-1">
                        <Calendar className="w-3 h-3" />
                        Follow up: {format(parseISO(log.follow_up_date), 'MMM d, h:mm a')}
                      </p>
                    )}
                  </div>
                ))
              )}
            </TabsContent>

            <TabsContent value="onboarding" className="space-y-3">
              <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-medium text-gray-300">
                    Checklist ({completedTasks}/{onboardingTasks.length})
                  </h3>
                  {onboardingTasks.length > 0 && (
                    <span className="text-sm text-gray-400">{progress}%</span>
                  )}
                </div>
                {onboardingTasks.length > 0 && (
                  <div className="w-full bg-gray-800 rounded-full h-1.5 mb-4">
                    <div
                      className="bg-indigo-600 h-1.5 rounded-full transition-all"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                )}
                <div className="space-y-2">
                  {onboardingTasks.map(task => (
                    <div key={task.id} className="flex items-center gap-3 group">
                      <Checkbox
                        checked={task.completed}
                        onCheckedChange={() => handleToggleTask(task)}
                        className="border-gray-600 data-[state=checked]:bg-indigo-600 data-[state=checked]:border-indigo-600"
                      />
                      <span className={`text-sm flex-1 ${task.completed ? 'line-through text-gray-500' : 'text-gray-300'}`}>
                        {task.task}
                      </span>
                      <button
                        onClick={() => handleDeleteTask(task.id)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-gray-600 hover:text-red-400"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2 mt-4">
                  <Input
                    value={newTaskText}
                    onChange={e => setNewTaskText(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleAddTask()}
                    placeholder="Add a task..."
                    className="bg-gray-800 border-gray-700 text-white h-8 text-sm flex-1"
                  />
                  <Button
                    onClick={handleAddTask}
                    size="sm"
                    className="bg-indigo-600 hover:bg-indigo-700 text-white h-8 px-3"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="notes">
              <NotesTab leadId={lead.id} initialNotes={lead.notes || ''} onSaved={(n) => setLead(p => ({ ...p, notes: n }))} />
            </TabsContent>
          </Tabs>
        </div>
      </div>

      <CallLogModal
        leadId={lead.id}
        open={callLogOpen}
        onOpenChange={setCallLogOpen}
        onSaved={(log) => setCallLogs(prev => [log, ...prev])}
      />
    </div>
  )
}

function NotesTab({ leadId, initialNotes, onSaved }: { leadId: string; initialNotes: string; onSaved: (n: string) => void }) {
  const supabase = createClient()
  const [notes, setNotes] = useState(initialNotes)
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    const { error } = await supabase.from('leads').update({ notes }).eq('id', leadId)
    setSaving(false)
    if (error) {
      toast.error(error.message)
      return
    }
    onSaved(notes)
    setDirty(false)
    toast.success('Notes saved!')
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
      <Textarea
        value={notes}
        onChange={e => { setNotes(e.target.value); setDirty(true) }}
        className="bg-gray-800 border-gray-700 text-white min-h-[200px] resize-none"
        placeholder="Add notes about this lead..."
      />
      {dirty && (
        <div className="flex justify-end">
          <Button
            onClick={handleSave}
            disabled={saving}
            size="sm"
            className="bg-indigo-600 hover:bg-indigo-700 text-white"
          >
            {saving ? 'Saving...' : 'Save Notes'}
          </Button>
        </div>
      )}
    </div>
  )
}

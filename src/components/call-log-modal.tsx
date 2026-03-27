'use client'

import { useState } from 'react'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'sonner'
import type { CallOutcome, CallLog } from '@/types'

interface CallLogModalProps {
  leadId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onSaved: (log: CallLog) => void
}

const OUTCOMES: { value: CallOutcome; label: string }[] = [
  { value: 'answered', label: 'Answered' },
  { value: 'voicemail', label: 'Left Voicemail' },
  { value: 'no_answer', label: 'No Answer' },
  { value: 'callback_scheduled', label: 'Callback Scheduled' },
  { value: 'not_interested', label: 'Not Interested' },
  { value: 'interested', label: 'Interested' },
  { value: 'quoted', label: 'Quoted' },
  { value: 'closed', label: 'Closed' },
]

export default function CallLogModal({ leadId, open, onOpenChange, onSaved }: CallLogModalProps) {
  const supabase = createClient()
  const [loading, setLoading] = useState(false)
  const [formData, setFormData] = useState({
    outcome: '' as CallOutcome | '',
    duration_minutes: '',
    notes: '',
    next_action: '',
    follow_up_date: '',
  })

  const handleChange = (field: string, value: string | null) => {
    setFormData(prev => ({ ...prev, [field]: value ?? '' }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.outcome) {
      toast.error('Please select a call outcome')
      return
    }
    setLoading(true)

    const { data: { user } } = await supabase.auth.getUser()

    const payload = {
      lead_id: leadId,
      called_by: user?.id || null,
      outcome: formData.outcome as CallOutcome,
      duration_minutes: formData.duration_minutes ? parseInt(formData.duration_minutes) : null,
      notes: formData.notes || null,
      next_action: formData.next_action || null,
      follow_up_date: formData.follow_up_date || null,
    }

    const { data, error } = await supabase
      .from('call_logs')
      .insert(payload)
      .select()
      .single()

    setLoading(false)

    if (error) {
      toast.error(error.message)
      return
    }

    // Update lead status based on outcome
    if (formData.outcome === 'answered' || formData.outcome === 'interested' || formData.outcome === 'callback_scheduled') {
      await supabase.from('leads').update({ status: 'contacted' }).eq('id', leadId)
    }
    if (formData.follow_up_date) {
      await supabase.from('leads').update({ next_follow_up: formData.follow_up_date }).eq('id', leadId)
    }

    toast.success('Call logged!')
    onSaved(data as CallLog)
    onOpenChange(false)
    setFormData({ outcome: '', duration_minutes: '', notes: '', next_action: '', follow_up_date: '' })
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-gray-900 border-gray-800 text-white max-w-md">
        <DialogHeader>
          <DialogTitle className="text-white">Log Call</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 mt-2">
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Outcome *</Label>
            <Select value={formData.outcome || ''} onValueChange={(v) => handleChange('outcome', v ?? '')}>
              <SelectTrigger className="bg-gray-800 border-gray-700 text-white">
                <SelectValue placeholder="Select outcome..." />
              </SelectTrigger>
              <SelectContent className="bg-gray-900 border-gray-700">
                {OUTCOMES.map(({ value, label }) => (
                  <SelectItem key={value} value={value} className="text-gray-200 focus:bg-gray-800">
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Duration (minutes)</Label>
            <Input
              type="number"
              value={formData.duration_minutes}
              onChange={(e) => handleChange('duration_minutes', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="5"
              min="0"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Notes</Label>
            <Textarea
              value={formData.notes}
              onChange={(e) => handleChange('notes', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white min-h-[80px]"
              placeholder="What was discussed..."
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Next Action</Label>
            <Input
              value={formData.next_action}
              onChange={(e) => handleChange('next_action', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="Send proposal, Call back Tuesday..."
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Follow-up Date</Label>
            <Input
              type="datetime-local"
              value={formData.follow_up_date}
              onChange={(e) => handleChange('follow_up_date', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
            />
          </div>

          <div className="flex gap-2 justify-end pt-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="border-gray-700 text-gray-300 hover:bg-gray-800"
            >
              Cancel
            </Button>
            <Button type="submit" disabled={loading} className="bg-indigo-600 hover:bg-indigo-700 text-white">
              {loading ? 'Saving...' : 'Log Call'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  )
}

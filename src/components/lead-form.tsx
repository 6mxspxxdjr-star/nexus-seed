'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { toast } from 'sonner'
import type { Lead, LeadStatus, LeadPriority } from '@/types'

interface LeadFormProps {
  lead?: Partial<Lead>
  onSuccess?: (lead: Lead) => void
  onCancel?: () => void
}

const SERVICE_TYPES = [
  'Commercial HVAC',
  'Residential HVAC',
  'Industrial HVAC',
  'Refrigeration',
  'Boiler/Heating',
  'Chiller Systems',
  'Building Automation',
  'Preventive Maintenance',
  'Emergency Service',
  'Other',
]

const SOURCES = [
  'Cold Call',
  'Referral',
  'Website',
  'LinkedIn',
  'Trade Show',
  'Door Knock',
  'Direct Mail',
  'Other',
]

export default function LeadForm({ lead, onSuccess, onCancel }: LeadFormProps) {
  const router = useRouter()
  const supabase = createClient()
  const [loading, setLoading] = useState(false)

  const [formData, setFormData] = useState({
    company_name: lead?.company_name || '',
    contact_name: lead?.contact_name || '',
    phone: lead?.phone || '',
    email: lead?.email || '',
    website: lead?.website || '',
    address: lead?.address || '',
    city: lead?.city || '',
    state: lead?.state || '',
    zip: lead?.zip || '',
    service_type: lead?.service_type || '',
    estimated_deal_size: lead?.estimated_deal_size?.toString() || '',
    employees_count: lead?.employees_count || '',
    status: lead?.status || 'new' as LeadStatus,
    priority: lead?.priority || 'medium' as LeadPriority,
    source: lead?.source || '',
    notes: lead?.notes || '',
    next_follow_up: lead?.next_follow_up ? lead.next_follow_up.slice(0, 16) : '',
  })

  const handleChange = (field: string, value: string | null) => {
    setFormData(prev => ({ ...prev, [field]: value ?? '' }))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)

    const payload = {
      company_name: formData.company_name,
      contact_name: formData.contact_name || null,
      phone: formData.phone || null,
      email: formData.email || null,
      website: formData.website || null,
      address: formData.address || null,
      city: formData.city || null,
      state: formData.state || null,
      zip: formData.zip || null,
      service_type: formData.service_type || null,
      estimated_deal_size: formData.estimated_deal_size ? parseFloat(formData.estimated_deal_size) : null,
      employees_count: formData.employees_count || null,
      status: formData.status,
      priority: formData.priority,
      source: formData.source || null,
      notes: formData.notes || null,
      next_follow_up: formData.next_follow_up || null,
    }

    let result
    if (lead?.id) {
      result = await supabase
        .from('leads')
        .update(payload)
        .eq('id', lead.id)
        .select()
        .single()
    } else {
      result = await supabase
        .from('leads')
        .insert(payload)
        .select()
        .single()
    }

    setLoading(false)

    if (result.error) {
      toast.error(result.error.message)
      return
    }

    toast.success(lead?.id ? 'Lead updated!' : 'Lead created!')

    if (onSuccess) {
      onSuccess(result.data as Lead)
    } else {
      router.push(`/leads/${result.data.id}`)
      router.refresh()
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Contact Info</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="col-span-2 space-y-1.5">
            <Label className="text-gray-300 text-sm">Company Name *</Label>
            <Input
              value={formData.company_name}
              onChange={(e) => handleChange('company_name', e.target.value)}
              required
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="ACME Corp"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Contact Name</Label>
            <Input
              value={formData.contact_name}
              onChange={(e) => handleChange('contact_name', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="John Smith"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Phone</Label>
            <Input
              value={formData.phone}
              onChange={(e) => handleChange('phone', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="(555) 123-4567"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Email</Label>
            <Input
              type="email"
              value={formData.email}
              onChange={(e) => handleChange('email', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="john@company.com"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Website</Label>
            <Input
              value={formData.website}
              onChange={(e) => handleChange('website', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="www.company.com"
            />
          </div>
          <div className="col-span-2 space-y-1.5">
            <Label className="text-gray-300 text-sm">Address</Label>
            <Input
              value={formData.address}
              onChange={(e) => handleChange('address', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="123 Main St"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">City</Label>
            <Input
              value={formData.city}
              onChange={(e) => handleChange('city', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1.5">
              <Label className="text-gray-300 text-sm">State</Label>
              <Input
                value={formData.state}
                onChange={(e) => handleChange('state', e.target.value)}
                className="bg-gray-800 border-gray-700 text-white"
                placeholder="CA"
                maxLength={2}
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-gray-300 text-sm">Zip</Label>
              <Input
                value={formData.zip}
                onChange={(e) => handleChange('zip', e.target.value)}
                className="bg-gray-800 border-gray-700 text-white"
                placeholder="90210"
              />
            </div>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Business Info</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Service Type</Label>
            <Select value={formData.service_type} onValueChange={(v) => handleChange('service_type', v)}>
              <SelectTrigger className="bg-gray-800 border-gray-700 text-white">
                <SelectValue placeholder="Select type..." />
              </SelectTrigger>
              <SelectContent className="bg-gray-900 border-gray-700">
                {SERVICE_TYPES.map(t => (
                  <SelectItem key={t} value={t} className="text-gray-200 focus:bg-gray-800">{t}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Est. Deal Size ($)</Label>
            <Input
              type="number"
              value={formData.estimated_deal_size}
              onChange={(e) => handleChange('estimated_deal_size', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="5000"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Employees</Label>
            <Input
              value={formData.employees_count}
              onChange={(e) => handleChange('employees_count', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
              placeholder="1-10"
            />
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Source</Label>
            <Select value={formData.source} onValueChange={(v) => handleChange('source', v)}>
              <SelectTrigger className="bg-gray-800 border-gray-700 text-white">
                <SelectValue placeholder="Select source..." />
              </SelectTrigger>
              <SelectContent className="bg-gray-900 border-gray-700">
                {SOURCES.map(s => (
                  <SelectItem key={s} value={s} className="text-gray-200 focus:bg-gray-800">{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </div>

      <div>
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">Pipeline</h3>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Status</Label>
            <Select value={formData.status} onValueChange={(v) => handleChange('status', v as LeadStatus)}>
              <SelectTrigger className="bg-gray-800 border-gray-700 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-gray-900 border-gray-700">
                {(['new', 'contacted', 'follow_up', 'quoted', 'closed_won', 'onboarding', 'active', 'dead'] as LeadStatus[]).map(s => (
                  <SelectItem key={s} value={s} className="text-gray-200 focus:bg-gray-800">
                    {s.charAt(0).toUpperCase() + s.slice(1).replace('_', ' ')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label className="text-gray-300 text-sm">Priority</Label>
            <Select value={formData.priority} onValueChange={(v) => handleChange('priority', v as LeadPriority)}>
              <SelectTrigger className="bg-gray-800 border-gray-700 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-gray-900 border-gray-700">
                <SelectItem value="low" className="text-gray-200 focus:bg-gray-800">Low</SelectItem>
                <SelectItem value="medium" className="text-gray-200 focus:bg-gray-800">Medium</SelectItem>
                <SelectItem value="high" className="text-gray-200 focus:bg-gray-800">High</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="col-span-2 space-y-1.5">
            <Label className="text-gray-300 text-sm">Next Follow-up</Label>
            <Input
              type="datetime-local"
              value={formData.next_follow_up}
              onChange={(e) => handleChange('next_follow_up', e.target.value)}
              className="bg-gray-800 border-gray-700 text-white"
            />
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label className="text-gray-300 text-sm">Notes</Label>
        <Textarea
          value={formData.notes}
          onChange={(e) => handleChange('notes', e.target.value)}
          className="bg-gray-800 border-gray-700 text-white min-h-[80px]"
          placeholder="Additional notes..."
        />
      </div>

      <div className="flex gap-2 justify-end pt-2">
        {onCancel && (
          <Button type="button" variant="outline" onClick={onCancel} className="border-gray-700 text-gray-300 hover:bg-gray-800">
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={loading} className="bg-indigo-600 hover:bg-indigo-700 text-white">
          {loading ? 'Saving...' : lead?.id ? 'Update Lead' : 'Create Lead'}
        </Button>
      </div>
    </form>
  )
}

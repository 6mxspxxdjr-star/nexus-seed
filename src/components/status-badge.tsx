import { Badge } from '@/components/ui/badge'
import type { LeadStatus, LeadPriority } from '@/types'

const statusConfig: Record<LeadStatus, { label: string; className: string }> = {
  new: { label: 'New', className: 'bg-gray-700 text-gray-200 hover:bg-gray-700' },
  contacted: { label: 'Contacted', className: 'bg-blue-900/50 text-blue-300 hover:bg-blue-900/50 border-blue-800' },
  follow_up: { label: 'Follow Up', className: 'bg-amber-900/50 text-amber-300 hover:bg-amber-900/50 border-amber-800' },
  quoted: { label: 'Quoted', className: 'bg-purple-900/50 text-purple-300 hover:bg-purple-900/50 border-purple-800' },
  closed_won: { label: 'Closed Won', className: 'bg-green-900/50 text-green-300 hover:bg-green-900/50 border-green-800' },
  onboarding: { label: 'Onboarding', className: 'bg-teal-900/50 text-teal-300 hover:bg-teal-900/50 border-teal-800' },
  active: { label: 'Active', className: 'bg-emerald-900/50 text-emerald-300 hover:bg-emerald-900/50 border-emerald-800' },
  dead: { label: 'Dead', className: 'bg-red-900/50 text-red-300 hover:bg-red-900/50 border-red-800' },
}

const priorityConfig: Record<LeadPriority, { label: string; className: string }> = {
  low: { label: 'Low', className: 'bg-gray-700 text-gray-300 hover:bg-gray-700' },
  medium: { label: 'Medium', className: 'bg-yellow-900/50 text-yellow-300 hover:bg-yellow-900/50 border-yellow-800' },
  high: { label: 'High', className: 'bg-red-900/50 text-red-300 hover:bg-red-900/50 border-red-800' },
}

interface StatusBadgeProps {
  status: LeadStatus
}

interface PriorityBadgeProps {
  priority: LeadPriority
}

export function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status]
  return (
    <Badge variant="outline" className={`text-xs font-medium border ${config.className}`}>
      {config.label}
    </Badge>
  )
}

export function PriorityBadge({ priority }: PriorityBadgeProps) {
  const config = priorityConfig[priority]
  return (
    <Badge variant="outline" className={`text-xs font-medium border ${config.className}`}>
      {config.label}
    </Badge>
  )
}

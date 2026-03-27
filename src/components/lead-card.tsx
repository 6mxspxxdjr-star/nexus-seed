'use client'

import Link from 'next/link'
import { Phone, User, Calendar, DollarSign } from 'lucide-react'
import { format, parseISO } from 'date-fns'
import type { Lead } from '@/types'
import { StatusBadge, PriorityBadge } from './status-badge'

interface LeadCardProps {
  lead: Lead
}

export default function LeadCard({ lead }: LeadCardProps) {
  return (
    <Link href={`/leads/${lead.id}`}>
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 hover:border-indigo-600 transition-colors cursor-pointer group">
        <div className="flex items-start justify-between mb-2">
          <h3 className="font-medium text-white text-sm group-hover:text-indigo-400 transition-colors line-clamp-1">
            {lead.company_name}
          </h3>
          <PriorityBadge priority={lead.priority} />
        </div>

        {lead.contact_name && (
          <div className="flex items-center gap-1.5 text-gray-400 text-xs mb-1.5">
            <User className="w-3 h-3 flex-shrink-0" />
            <span className="truncate">{lead.contact_name}</span>
          </div>
        )}

        {lead.phone && (
          <div className="flex items-center gap-1.5 text-gray-400 text-xs mb-1.5">
            <Phone className="w-3 h-3 flex-shrink-0" />
            <span>{lead.phone}</span>
          </div>
        )}

        {lead.estimated_deal_size && (
          <div className="flex items-center gap-1.5 text-gray-400 text-xs mb-1.5">
            <DollarSign className="w-3 h-3 flex-shrink-0" />
            <span>${lead.estimated_deal_size.toLocaleString()}</span>
          </div>
        )}

        {lead.next_follow_up && (
          <div className="flex items-center gap-1.5 text-amber-400 text-xs mb-2">
            <Calendar className="w-3 h-3 flex-shrink-0" />
            <span>{format(parseISO(lead.next_follow_up), 'MMM d')}</span>
          </div>
        )}

        <div className="mt-2">
          <StatusBadge status={lead.status} />
        </div>
      </div>
    </Link>
  )
}

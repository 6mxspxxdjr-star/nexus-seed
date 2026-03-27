'use client'

import { Check } from 'lucide-react'
import { createClient } from '@/lib/supabase/client'
import { toast } from 'sonner'
import type { LeadStatus } from '@/types'

const PIPELINE_STEPS: { status: LeadStatus; label: string }[] = [
  { status: 'new', label: 'New' },
  { status: 'contacted', label: 'Contacted' },
  { status: 'follow_up', label: 'Follow Up' },
  { status: 'quoted', label: 'Quoted' },
  { status: 'closed_won', label: 'Closed Won' },
  { status: 'onboarding', label: 'Onboarding' },
  { status: 'active', label: 'Active' },
]

const STATUS_ORDER: LeadStatus[] = ['new', 'contacted', 'follow_up', 'quoted', 'closed_won', 'onboarding', 'active', 'dead']

interface PipelineStepperProps {
  leadId: string
  currentStatus: LeadStatus
  onStatusChange: (status: LeadStatus) => void
}

export default function PipelineStepper({ leadId, currentStatus, onStatusChange }: PipelineStepperProps) {
  const supabase = createClient()

  const currentIndex = STATUS_ORDER.indexOf(currentStatus)

  const handleStepClick = async (status: LeadStatus) => {
    if (status === currentStatus) return

    const { error } = await supabase
      .from('leads')
      .update({ status })
      .eq('id', leadId)

    if (error) {
      toast.error(error.message)
      return
    }

    onStatusChange(status)
    toast.success(`Status updated to ${status.replace('_', ' ')}`)
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-4">Pipeline Stage</h3>
      <div className="flex items-center gap-0">
        {PIPELINE_STEPS.map((step, index) => {
          const stepIndex = STATUS_ORDER.indexOf(step.status)
          const isCompleted = currentStatus !== 'dead' && stepIndex < currentIndex
          const isCurrent = step.status === currentStatus
          const isClickable = step.status !== currentStatus

          return (
            <div key={step.status} className="flex items-center flex-1">
              <button
                onClick={() => isClickable && handleStepClick(step.status)}
                className={`flex flex-col items-center gap-1.5 flex-1 group ${isClickable ? 'cursor-pointer' : 'cursor-default'}`}
              >
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-all ${
                    isCurrent
                      ? 'bg-indigo-600 text-white ring-2 ring-indigo-400 ring-offset-2 ring-offset-gray-900'
                      : isCompleted
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-800 text-gray-400 border border-gray-700 group-hover:border-gray-500'
                  }`}
                >
                  {isCompleted ? <Check className="w-4 h-4" /> : index + 1}
                </div>
                <span
                  className={`text-xs text-center hidden sm:block ${
                    isCurrent ? 'text-indigo-400 font-medium' : isCompleted ? 'text-green-400' : 'text-gray-500'
                  }`}
                >
                  {step.label}
                </span>
              </button>
              {index < PIPELINE_STEPS.length - 1 && (
                <div className={`h-0.5 flex-1 mx-1 ${isCompleted ? 'bg-green-600' : 'bg-gray-700'}`} />
              )}
            </div>
          )
        })}
      </div>
      {currentStatus === 'dead' && (
        <div className="mt-3 flex items-center justify-center">
          <span className="text-xs font-medium text-red-400 bg-red-900/30 border border-red-800 rounded px-2 py-1">
            Dead Lead
          </span>
        </div>
      )}
    </div>
  )
}

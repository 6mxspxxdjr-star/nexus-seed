'use client'

import { useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { createClient } from '@/lib/supabase/client'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Progress } from '@/components/ui/progress'
import { Upload, FileText, X, CheckCircle2, AlertCircle } from 'lucide-react'
import { toast } from 'sonner'

const LEAD_FIELDS = [
  { value: 'company_name', label: 'Company Name *' },
  { value: 'contact_name', label: 'Contact Name' },
  { value: 'phone', label: 'Phone' },
  { value: 'email', label: 'Email' },
  { value: 'website', label: 'Website' },
  { value: 'address', label: 'Address' },
  { value: 'city', label: 'City' },
  { value: 'state', label: 'State' },
  { value: 'zip', label: 'Zip' },
  { value: 'service_type', label: 'Service Type' },
  { value: 'estimated_deal_size', label: 'Est. Deal Size' },
  { value: 'employees_count', label: 'Employees' },
  { value: 'source', label: 'Source' },
  { value: 'notes', label: 'Notes' },
  { value: 'skip', label: '— Skip this column —' },
]

function parseCSV(text: string): { headers: string[]; rows: string[][] } {
  const lines = text.trim().split('\n')
  const headers = lines[0].split(',').map(h => h.trim().replace(/^"|"$/g, ''))
  const rows = lines.slice(1).map(line => {
    const result: string[] = []
    let current = ''
    let inQuotes = false
    for (let i = 0; i < line.length; i++) {
      if (line[i] === '"') {
        inQuotes = !inQuotes
      } else if (line[i] === ',' && !inQuotes) {
        result.push(current.trim())
        current = ''
      } else {
        current += line[i]
      }
    }
    result.push(current.trim())
    return result
  })
  return { headers, rows }
}

function autoMap(header: string): string {
  const h = header.toLowerCase().replace(/[\s_-]/g, '')
  if (h.includes('company') || h === 'business' || h === 'name') return 'company_name'
  if (h.includes('contact') || h.includes('person') || h.includes('firstname') || h.includes('lastname')) return 'contact_name'
  if (h.includes('phone') || h.includes('tel') || h.includes('mobile')) return 'phone'
  if (h.includes('email') || h.includes('mail')) return 'email'
  if (h.includes('website') || h.includes('url') || h.includes('web')) return 'website'
  if (h.includes('address') || h.includes('street')) return 'address'
  if (h.includes('city')) return 'city'
  if (h.includes('state') || h.includes('province')) return 'state'
  if (h.includes('zip') || h.includes('postal')) return 'zip'
  if (h.includes('service') || h.includes('type')) return 'service_type'
  if (h.includes('deal') || h.includes('size') || h.includes('value') || h.includes('amount')) return 'estimated_deal_size'
  if (h.includes('employee') || h.includes('staff') || h.includes('size')) return 'employees_count'
  if (h.includes('source') || h.includes('lead source')) return 'source'
  if (h.includes('note') || h.includes('comment')) return 'notes'
  return 'skip'
}

export default function ImportMapper() {
  const router = useRouter()
  const supabase = createClient()
  const [dragging, setDragging] = useState(false)
  const [file, setFile] = useState<File | null>(null)
  const [headers, setHeaders] = useState<string[]>([])
  const [rows, setRows] = useState<string[][]>([])
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [importing, setImporting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [result, setResult] = useState<{ success: number; failed: number } | null>(null)

  const processFile = useCallback((f: File) => {
    setFile(f)
    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      const { headers, rows } = parseCSV(text)
      setHeaders(headers)
      setRows(rows)
      const autoMapping: Record<string, string> = {}
      headers.forEach(h => {
        autoMapping[h] = autoMap(h)
      })
      setMapping(autoMapping)
      setResult(null)
    }
    reader.readAsText(f)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f && f.name.endsWith('.csv')) {
      processFile(f)
    } else {
      toast.error('Please upload a CSV file')
    }
  }, [processFile])

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) processFile(f)
  }

  const handleImport = async () => {
    const companyCol = Object.entries(mapping).find(([, v]) => v === 'company_name')?.[0]
    if (!companyCol) {
      toast.error('Please map the Company Name column')
      return
    }

    setImporting(true)
    setProgress(0)

    let success = 0
    let failed = 0
    const batchSize = 10

    for (let i = 0; i < rows.length; i += batchSize) {
      const batch = rows.slice(i, i + batchSize)
      const leads = batch.map(row => {
        const lead: Record<string, string | number | null> = {}
        headers.forEach((h, idx) => {
          const field = mapping[h]
          if (!field || field === 'skip') return
          const val = row[idx]?.trim() || null
          if (field === 'estimated_deal_size') {
            lead[field] = val ? parseFloat(val.replace(/[$,]/g, '')) : null
          } else {
            lead[field] = val
          }
        })
        if (!lead.company_name) return null
        lead.status = 'new'
        lead.priority = 'medium'
        return lead
      }).filter(Boolean)

      if (leads.length > 0) {
        const { data, error } = await supabase.from('leads').insert(leads).select('id')
        if (error) {
          failed += leads.length
        } else {
          success += data.length
        }
      }

      setProgress(Math.round(((i + batchSize) / rows.length) * 100))
    }

    setImporting(false)
    setProgress(100)
    setResult({ success, failed })

    if (success > 0) {
      toast.success(`Imported ${success} leads!`)
      setTimeout(() => {
        router.push('/leads')
        router.refresh()
      }, 1500)
    }
  }

  return (
    <div className="space-y-6">
      {!file ? (
        <div
          onDrop={handleDrop}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          className={`border-2 border-dashed rounded-xl p-12 text-center transition-colors ${
            dragging ? 'border-indigo-500 bg-indigo-950/20' : 'border-gray-700 hover:border-gray-600'
          }`}
        >
          <Upload className="w-10 h-10 text-gray-500 mx-auto mb-3" />
          <p className="text-gray-300 font-medium mb-1">Drop your CSV file here</p>
          <p className="text-gray-500 text-sm mb-4">or click to browse</p>
          <label className="cursor-pointer">
            <span className="bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-md transition-colors">
              Choose File
            </span>
            <input type="file" accept=".csv" onChange={handleFileInput} className="hidden" />
          </label>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex items-center justify-between bg-gray-900 border border-gray-800 rounded-lg p-3">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 bg-indigo-600/20 rounded-md flex items-center justify-center">
                <FileText className="w-5 h-5 text-indigo-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-white">{file.name}</p>
                <p className="text-xs text-gray-400">{rows.length} rows, {headers.length} columns</p>
              </div>
            </div>
            <button
              onClick={() => { setFile(null); setHeaders([]); setRows([]); setResult(null) }}
              className="text-gray-500 hover:text-gray-300 transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {result ? (
            <div className={`flex items-center gap-3 p-4 rounded-lg border ${
              result.failed === 0 ? 'bg-green-900/20 border-green-800' : 'bg-amber-900/20 border-amber-800'
            }`}>
              {result.failed === 0
                ? <CheckCircle2 className="w-5 h-5 text-green-400 flex-shrink-0" />
                : <AlertCircle className="w-5 h-5 text-amber-400 flex-shrink-0" />
              }
              <div>
                <p className="text-sm font-medium text-white">
                  Import complete: {result.success} succeeded, {result.failed} failed
                </p>
                <p className="text-xs text-gray-400">Redirecting to leads...</p>
              </div>
            </div>
          ) : (
            <>
              <div>
                <h3 className="text-sm font-semibold text-gray-300 mb-3">Map Columns</h3>
                <div className="grid grid-cols-2 gap-2">
                  {headers.map(header => (
                    <div key={header} className="flex items-center gap-2">
                      <span className="text-sm text-gray-400 min-w-0 flex-1 truncate">{header}</span>
                      <div className="w-44">
                        <Select
                          value={mapping[header] || 'skip'}
                          onValueChange={(v) => setMapping(prev => ({ ...prev, [header]: v ?? 'skip' }))}
                        >
                          <SelectTrigger className="bg-gray-800 border-gray-700 text-white h-8 text-xs">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-gray-900 border-gray-700">
                            {LEAD_FIELDS.map(f => (
                              <SelectItem key={f.value} value={f.value} className="text-gray-200 focus:bg-gray-800 text-xs">
                                {f.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-gray-300 mb-3">Preview (first 5 rows)</h3>
                <div className="overflow-x-auto rounded-lg border border-gray-800">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-gray-800 bg-gray-900">
                        {headers.map(h => (
                          <th key={h} className="text-left px-3 py-2 text-gray-400 font-medium whitespace-nowrap">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {rows.slice(0, 5).map((row, i) => (
                        <tr key={i} className="border-b border-gray-800/50 hover:bg-gray-800/50">
                          {row.map((cell, j) => (
                            <td key={j} className="px-3 py-2 text-gray-300 whitespace-nowrap max-w-[150px] truncate">{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {importing && (
                <div className="space-y-2">
                  <div className="flex justify-between text-sm text-gray-400">
                    <span>Importing...</span>
                    <span>{progress}%</span>
                  </div>
                  <Progress value={progress} className="h-2" />
                </div>
              )}

              <div className="flex justify-end">
                <Button
                  onClick={handleImport}
                  disabled={importing || rows.length === 0}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white"
                >
                  {importing ? 'Importing...' : `Import ${rows.length} Leads`}
                </Button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}

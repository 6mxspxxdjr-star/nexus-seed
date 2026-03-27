import ImportMapper from '@/components/import-mapper'

export default function ImportPage() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Import Leads</h1>
        <p className="text-gray-400 text-sm mt-0.5">Upload a CSV file to bulk import leads into LeadFlow</p>
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6">
        <ImportMapper />
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">CSV Format Tips</h3>
        <ul className="space-y-1.5 text-sm text-gray-400">
          <li className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full flex-shrink-0" />
            First row should be column headers
          </li>
          <li className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full flex-shrink-0" />
            <span><strong className="text-gray-300">Company Name</strong> is the only required field</span>
          </li>
          <li className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full flex-shrink-0" />
            Column mapping is auto-detected but can be customized
          </li>
          <li className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full flex-shrink-0" />
            All imported leads start with &quot;New&quot; status and &quot;Medium&quot; priority
          </li>
          <li className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full flex-shrink-0" />
            Deal size should be a number (e.g., 5000 or $5,000)
          </li>
        </ul>
      </div>
    </div>
  )
}

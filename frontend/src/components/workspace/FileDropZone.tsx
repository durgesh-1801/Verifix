import type { ChangeEvent, DragEvent } from 'react'

export function FileDropZone({
  label,
  hint,
  file,
  onFile,
  disabled,
  accent,
}: {
  label: string
  hint: string
  file: File | null
  onFile: (f: File | null) => void
  disabled?: boolean
  accent: 'violet' | 'slate'
}) {
  const border =
    accent === 'violet'
      ? 'border-[#5B3DF5]/30 hover:border-[#5B3DF5]/50 focus-within:border-[#5B3DF5]'
      : 'border-slate-200 hover:border-slate-300 focus-within:border-slate-400'

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    onFile(e.target.files?.[0] ?? null)
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    if (disabled) return
    const f = e.dataTransfer.files?.[0]
    if (f) onFile(f)
  }

  return (
    <label
      className={`relative block cursor-pointer rounded-xl border-2 border-dashed bg-[#FAFBFC] px-4 py-6 transition ${border} ${disabled ? 'pointer-events-none opacity-60' : ''}`}
      onDragOver={(e: DragEvent) => e.preventDefault()}
      onDrop={onDrop}
    >
      <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</span>
      <p className="mt-1 text-sm text-slate-600">{hint}</p>
      <p className="mt-3 truncate text-sm font-medium text-[#1A1C2E]">
        {file ? file.name : 'No file selected'}
      </p>
      <input
        type="file"
        accept=".pdf,.txt"
        className="absolute inset-0 cursor-pointer opacity-0"
        onChange={onChange}
        disabled={disabled}
      />
    </label>
  )
}

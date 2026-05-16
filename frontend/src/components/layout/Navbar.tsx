import type { ReactNode } from 'react'
import { LogoMark } from '../ui/LogoMark'
import { scrollToId } from '../../lib/scroll'

const NAV = [
  { label: 'Ledger', id: 'hero' },
  { label: 'Verification', id: 'workspace' },
  { label: 'Pipelines', id: 'pipeline' },
  { label: 'Reports', id: 'workspace' },
] as const

function IconButton({ label, children }: { label: string; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition hover:bg-slate-50 hover:text-slate-800"
    >
      {children}
    </button>
  )
}

export function Navbar({ onOpenWorkspace }: { onOpenWorkspace: () => void }) {
  return (
    <header className="sticky top-0 z-50 border-b border-gray-100 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-3 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={() => scrollToId('top')}
          className="flex items-center gap-2.5 rounded-lg outline-none ring-[#5B3DF5] focus-visible:ring-2"
        >
          <LogoMark />
          <span className="text-base font-bold tracking-tight text-[#1A1C2E]">Invoice AI</span>
        </button>

        <nav className="hidden items-center gap-8 md:flex" aria-label="Product">
          {NAV.map((item) => (
            <button
              key={item.label}
              type="button"
              onClick={() => scrollToId(item.id)}
              className="text-[11px] font-semibold tracking-[0.12em] text-slate-400 transition hover:text-slate-700"
            >
              {item.label.toUpperCase()}
            </button>
          ))}
        </nav>

        <div className="flex items-center gap-1 sm:gap-2">
          <IconButton label="Help">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <circle cx="12" cy="12" r="10" />
              <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01" />
            </svg>
          </IconButton>
          <IconButton label="Notifications">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
          </IconButton>
          <IconButton label="Settings">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75">
              <circle cx="12" cy="12" r="3" />
              <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
            </svg>
          </IconButton>
          <button
            type="button"
            onClick={onOpenWorkspace}
            className="ml-1 rounded-lg bg-[#5B3DF5] px-3 py-2 text-[10px] font-semibold tracking-wide text-white shadow-sm shadow-[#5B3DF5]/25 transition hover:bg-[#4a32c8] sm:px-4 sm:text-xs"
          >
            OPEN WORKSPACE
          </button>
        </div>
      </div>
    </header>
  )
}

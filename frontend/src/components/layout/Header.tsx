import { useState } from 'react'

interface HeaderProps {
  onMobileMenuToggle?: () => void
}

export function Header({ onMobileMenuToggle }: HeaderProps) {
  const [themeMode, setThemeMode] = useState<'light' | 'dark'>('light')

  const toggleTheme = () => {
    setThemeMode((prev) => (prev === 'light' ? 'dark' : 'light'))
  }

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-slate-100 bg-white/80 px-4 sm:px-6 backdrop-blur-md">
      
      {/* Left items: Mobile menu, Workspace selector & Sandbox badge */}
      <div className="flex items-center gap-3">
        {/* Mobile menu trigger */}
        <button
          type="button"
          onClick={onMobileMenuToggle}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-500 hover:bg-slate-50 lg:hidden"
          aria-label="Open navigation menu"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <line x1="4" y1="12" x2="20" y2="12" />
            <line x1="4" y1="6" x2="20" y2="6" />
            <line x1="4" y1="18" x2="20" y2="18" />
          </svg>
        </button>

        {/* Active Workspace Selector Dropdown */}
        <div className="relative">
          <button
            type="button"
            className="flex items-center gap-2 rounded-lg border border-slate-100 bg-slate-50/50 px-3 py-1.5 text-xs font-semibold text-[#1A1C2E] hover:bg-slate-50 transition"
          >
            <span className="h-2 w-2 rounded-full bg-[#5B3DF5]" />
            Enterprise Ledger
            <svg className="h-3.5 w-3.5 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </button>
        </div>

        {/* Compliance pill */}
        <span className="hidden sm:inline-flex items-center gap-1 rounded-md bg-slate-50 border border-slate-100 px-2 py-1 text-[9px] font-bold tracking-wider text-slate-400 uppercase">
          <svg className="h-3 w-3 text-slate-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
            <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          </svg>
          SOC2 Certified Sandbox
        </span>
      </div>

      {/* Middle & Right items: Search, theme, alerts, profile */}
      <div className="flex items-center gap-4 sm:gap-6">
        
        {/* Search Bar */}
        <div className="relative hidden md:block w-72 lg:w-96">
          <span className="absolute inset-y-0 left-3 flex items-center text-slate-400">
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
          </span>
          <input
            type="text"
            placeholder="Search invoice IDs, discrepancy reports, audit logs..."
            className="w-full rounded-xl border border-slate-200 py-1.5 pl-10 pr-4 text-xs text-[#1A1C2E] placeholder-slate-400 outline-none transition focus:border-violet-500 focus:bg-white"
          />
        </div>

        {/* Theme toggler */}
        <button
          type="button"
          onClick={toggleTheme}
          className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-50 hover:text-slate-700 transition"
          aria-label={themeMode === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
        >
          {themeMode === 'light' ? (
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="5" />
              <line x1="12" y1="1" x2="12" y2="3" />
              <line x1="12" y1="21" x2="12" y2="23" />
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
              <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
              <line x1="1" y1="12" x2="3" y2="12" />
              <line x1="21" y1="12" x2="23" y2="12" />
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
              <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
            </svg>
          ) : (
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
            </svg>
          )}
        </button>

        {/* Notification Bell */}
        <button
          type="button"
          className="relative flex h-9 w-9 items-center justify-center rounded-lg text-slate-400 hover:bg-slate-50 hover:text-slate-700 transition"
          aria-label="View notifications"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          {/* Active notification indicator dot */}
          <span className="absolute right-2.5 top-2.5 h-1.5 w-1.5 rounded-full bg-[#5B3DF5]" />
        </button>

        {/* User initials circle avatar */}
        <div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-700 ring-2 ring-slate-100">
          DS
        </div>
      </div>
    </header>
  )
}
export default Header

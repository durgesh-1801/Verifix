import { NavLink, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { LogoMark } from '../ui/LogoMark'

const NAV_ITEMS = [
  {
    label: 'DASHBOARD',
    path: '/dashboard',
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <rect x="3" y="3" width="7" height="9" rx="1" />
        <rect x="14" y="3" width="7" height="5" rx="1" />
        <rect x="14" y="12" width="7" height="9" rx="1" />
        <rect x="3" y="16" width="7" height="5" rx="1" />
      </svg>
    ),
  },
  {
    label: 'UPLOAD VERIFICATION',
    path: '/workspace',
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M17 8l-5-5-5 5M12 3v12" />
      </svg>
    ),
  },
  {
    label: 'REPORTS',
    path: '/reports',
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <path d="M14 2v6h6" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
        <polyline points="10 9 9 9 8 9" />
      </svg>
    ),
  },
  {
    label: 'VENDORS',
    path: '/vendors',
    badge: '5',
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    label: 'AUDIT LOGS',
    path: '/logs',
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 12 16 14" />
      </svg>
    ),
  },
] as const

const SYSTEM_ITEMS = [
  {
    label: 'SETTINGS',
    path: '/settings',
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
      </svg>
    ),
  },
  {
    label: 'SUPPORT',
    path: '/support',
    icon: (
      <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>
    ),
  },
] as const

interface SidebarProps {
  onToggleCollapse?: (collapsed: boolean) => void
  isMobileOpen?: boolean
  onMobileClose?: () => void
}

export function Sidebar({ onToggleCollapse, isMobileOpen = false, onMobileClose }: SidebarProps) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const navigate = useNavigate()

  const handleCollapseToggle = () => {
    const nextState = !isCollapsed
    setIsCollapsed(nextState)
    if (onToggleCollapse) {
      onToggleCollapse(nextState)
    }
  }

  const handleLogout = () => {
    navigate('/login')
  }

  const sidebarClass = `
    fixed inset-y-0 left-0 z-40 flex flex-col justify-between border-r border-slate-100 bg-white transition-all duration-300 ease-in-out
    ${isCollapsed ? 'w-20' : 'w-64'}
    ${isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
    lg:static
  `

  return (
    <>
      {/* Mobile Sidebar Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-sm lg:hidden"
          onClick={onMobileClose}
        />
      )}

      <aside className={sidebarClass} aria-label="Sidebar Navigation">
        {/* Upper section */}
        <div>
          {/* Logo Brand Header */}
          <div className="flex h-16 items-center justify-between px-4 border-b border-slate-50">
            <NavLink to="/dashboard" className="flex items-center gap-2.5 rounded-lg outline-none">
              <LogoMark className="h-8 w-8" />
              {!isCollapsed && (
                <span className="text-base font-bold tracking-tight text-[#1A1C2E] transition-opacity duration-300">
                  Invoice AI
                </span>
              )}
            </NavLink>
            <button
              type="button"
              onClick={handleCollapseToggle}
              className="hidden lg:flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 text-slate-400 hover:bg-slate-50 hover:text-slate-700"
              aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              <svg
                className={`h-4 w-4 transform transition-transform duration-300 ${isCollapsed ? 'rotate-180' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth="2.5"
              >
                <polyline points="15 18 9 12 15 6" />
              </svg>
            </button>
          </div>

          {/* Navigation Items */}
          <nav className="mt-6 px-3" aria-label="Main Navigation">
            <ul className="space-y-1.5">
              {NAV_ITEMS.map((item) => (
                <li key={item.label}>
                  <NavLink
                    to={item.path}
                    onClick={onMobileClose}
                    className={({ isActive }) => `
                      flex items-center justify-between gap-3 rounded-xl px-3.5 py-3 text-xs font-semibold tracking-wide transition-all
                      ${
                        isActive
                          ? 'bg-[#5B3DF5]/8 text-[#5B3DF5]'
                          : 'text-slate-400 hover:bg-slate-50 hover:text-slate-700'
                      }
                    `}
                  >
                    <div className="flex items-center gap-3">
                      <span className="shrink-0">{item.icon}</span>
                      {!isCollapsed && <span className="truncate">{item.label}</span>}
                    </div>
                    {!isCollapsed && 'badge' in item && item.badge && (
                      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#5B3DF5]/10 text-[10px] font-bold text-[#5B3DF5]">
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>

            {/* System Section */}
            <div className="mt-8">
              {!isCollapsed && (
                <p className="px-3 text-[10px] font-bold tracking-widest text-slate-400 uppercase">
                  System
                </p>
              )}
              <ul className="mt-2 space-y-1.5">
                {SYSTEM_ITEMS.map((item) => (
                  <li key={item.label}>
                    <NavLink
                      to={item.path}
                      onClick={onMobileClose}
                      className={({ isActive }) => `
                        flex items-center gap-3 rounded-xl px-3.5 py-3 text-xs font-semibold tracking-wide transition-all
                        ${
                          isActive
                            ? 'bg-[#5B3DF5]/8 text-[#5B3DF5]'
                            : 'text-slate-400 hover:bg-slate-50 hover:text-slate-700'
                        }
                      `}
                    >
                      <span className="shrink-0">{item.icon}</span>
                      {!isCollapsed && <span className="truncate">{item.label}</span>}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          </nav>
        </div>

        {/* Profile Card at bottom */}
        <div className="border-t border-slate-100 p-4">
          <div className="flex items-center justify-between gap-2.5">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[#5B3DF5] text-xs font-bold text-white">
                DS
              </div>
              {!isCollapsed && (
                <div className="min-w-0">
                  <p className="truncate text-xs font-bold text-[#1A1C2E]">Durgesh Sharma</p>
                  <p className="truncate text-[10px] text-slate-400">test@gmail.com</p>
                </div>
              )}
            </div>
            {!isCollapsed && (
              <button
                type="button"
                onClick={handleLogout}
                className="shrink-0 text-[10px] font-bold uppercase tracking-wider text-rose-500 hover:text-rose-600 transition"
              >
                OUT
              </button>
            )}
          </div>
        </div>
      </aside>
    </>
  )
}
export default Sidebar

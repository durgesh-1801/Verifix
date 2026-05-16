export function LogoMark({ className = '' }: { className?: string }) {
  return (
    <div
      className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#5B3DF5] shadow-sm shadow-[#5B3DF5]/20 ${className}`}
      aria-hidden
    >
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="2" y="2" width="5" height="5" rx="1" fill="white" fillOpacity="0.95" />
        <rect x="9" y="2" width="5" height="5" rx="1" fill="white" fillOpacity="0.7" />
        <rect x="2" y="9" width="5" height="5" rx="1" fill="white" fillOpacity="0.7" />
        <rect x="9" y="9" width="5" height="5" rx="1" fill="white" fillOpacity="0.5" />
      </svg>
    </div>
  )
}

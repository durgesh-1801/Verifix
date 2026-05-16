export function Spinner({ className = 'border-white border-t-transparent' }: { className?: string }) {
  return (
    <span
      className={`inline-block h-5 w-5 animate-spin rounded-full border-2 ${className}`}
      aria-hidden
    />
  )
}

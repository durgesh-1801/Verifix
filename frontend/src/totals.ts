import type { Discrepancy } from './types'

/** Mirrors Flask `verify_route` total_difference aggregation. */
export function sumRupeeDifference(discrepancies: Discrepancy[]): number {
  let total = 0
  for (const d of discrepancies) {
    const diff = d.difference
    if (diff == null || diff === 'N/A') continue
    try {
      total += parseFloat(String(diff))
    } catch {
      /* ignore */
    }
  }
  if (total === Math.floor(total)) return Math.floor(total)
  return total
}

export function verificationStatusFrom(discrepancies: Discrepancy[]): 'Matched ✅' | 'Discrepancies Found' {
  return discrepancies.length > 0 ? 'Discrepancies Found' : 'Matched ✅'
}

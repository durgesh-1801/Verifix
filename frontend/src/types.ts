export type Discrepancy = {
  item: string
  field: string
  invoice: string
  po: string
  issue: string
  difference?: string
}

export type VerifySuccessResponse = {
  status: string
  total_issues: number
  total_rupee_difference: number
  discrepancies: Discrepancy[]
}

export type VerifyErrorBody = {
  error: string
  discrepancies?: Discrepancy[]
}

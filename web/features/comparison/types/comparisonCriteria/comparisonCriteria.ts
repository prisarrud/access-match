export type ComparisonCriteria = {
  stepFree: boolean
  ramp: boolean
  minimumClearWidthCm: number | null
}

export type ComparisonRequest = {
  propertyIds: [string, string]
  criteria: ComparisonCriteria
}

export type ComparisonSubmission = {
  values: { stepFree: boolean, ramp: boolean, width: string }
} & (
  | { status: 'idle' }
  | { status: 'invalid', errors: { width?: string, criteria?: string } }
  | { status: 'valid', request: ComparisonRequest }
)

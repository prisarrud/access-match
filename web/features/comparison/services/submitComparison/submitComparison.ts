import type { ComparisonRequest, ComparisonResponse } from '../../types'

type SubmissionResult =
  | { status: 'success', comparison: ComparisonResponse }
  | { status: 'unavailable' }
  | { status: 'error' }

export async function submitComparison(
  request: ComparisonRequest, comparisonId?: string, signal?: AbortSignal,
): Promise<SubmissionResult> {
  const baseUrl = process.env.API_BASE_URL

  if (!baseUrl) return { status: 'error' }

  if (comparisonId !== undefined && !/^[a-f0-9]{32}$/.test(comparisonId)) {
    return { status: 'unavailable' }
  }

  const requestId = crypto.randomUUID()

  try {
    const path = comparisonId === undefined
      ? 'comparisons'
      : `comparisons/${encodeURIComponent(comparisonId)}/recalculate`

    const response = await fetch(new URL(path, `${baseUrl.replace(/\/+$/, '')}/`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Request-ID': requestId },
      body: JSON.stringify(request),
      cache: 'no-store',
      signal: AbortSignal.any([
        AbortSignal.timeout(comparisonId === undefined ? 300_000 : 10_000),
        ...(signal ? [signal] : []),
      ]),
    })

    if (comparisonId !== undefined && response.status === 410) return { status: 'unavailable' }

    if (!response.ok) return { status: 'error' }

    const comparison: ComparisonResponse = await response.json()

    if (!comparison.comparisonId || !Array.isArray(comparison.properties)) return { status: 'error' }

    return { status: 'success', comparison }
  } catch {
    return { status: 'error' }
  }
}

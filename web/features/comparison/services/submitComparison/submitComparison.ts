import type { ComparisonRequest, ComparisonResponse } from '../../types'

export async function submitComparison(request: ComparisonRequest): Promise<ComparisonResponse | null> {
  const baseUrl = process.env.API_BASE_URL

  if (!baseUrl) return null

  try {
    const response = await fetch(new URL('comparisons', `${baseUrl.replace(/\/+$/, '')}/`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
      cache: 'no-store',
      signal: AbortSignal.timeout(300_000),
    })

    if (!response.ok) return null

    const result: ComparisonResponse = await response.json()
  
    return Array.isArray(result.properties) ? result : null
  } catch {
    return null
  }
}

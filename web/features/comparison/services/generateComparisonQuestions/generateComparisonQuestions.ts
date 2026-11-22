'use server'

import type { ComparisonRequest, CriterionResult } from '../../types'

type GeneratedQuestion = { pending: CriterionResult['toConfirm'][number], question: string }

type GenerationResult =
  | { status: 'success', questions: GeneratedQuestion[] }
  | { status: 'unavailable' }
  | { status: 'error' }

export async function generateComparisonQuestions(
  comparisonId: string, request: ComparisonRequest, propertyId: string,
): Promise<GenerationResult> {
  const baseUrl = process.env.API_BASE_URL

  if (!/^[a-f0-9]{32}$/.test(comparisonId)) return { status: 'unavailable' }
  if (!baseUrl) return { status: 'error' }

  try {
    const response = await fetch(new URL(`comparisons/${comparisonId}/questions`, `${baseUrl.replace(/\/+$/, '')}/`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...request, propertyId }),
      cache: 'no-store',
      signal: AbortSignal.timeout(130_000),
    })

    if (response.status === 410) return { status: 'unavailable' }
    if (!response.ok) return { status: 'error' }

    const result = await response.json()
    if (result.propertyId !== propertyId || !Array.isArray(result.questions) || result.questions.length === 0) {
      return { status: 'error' }
    }

    return { status: 'success', questions: result.questions }
  } catch {
    return { status: 'error' }
  }
}

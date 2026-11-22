import { hasTwoPropertyIds, propertyQueryParam } from '@/features/property-access-comparison'
import { submitComparison } from '@/features/comparison/services'
import { readComparisonSubmission } from '@/features/comparison/utils'

export async function POST(request: Request) {
  const params = new URLSearchParams(await request.text())
  const ids = params.getAll(propertyQueryParam)

  if (!hasTwoPropertyIds(ids) || ids[0] === ids[1]) {
    return Response.json({ status: 'error' }, { status: 400 })
  }

  const submission = readComparisonSubmission(ids, Object.fromEntries(params))
  if (submission.status !== 'valid') {
    return Response.json({ status: 'error' }, { status: 400 })
  }

  const comparisonId = params.get('comparacao') ?? undefined
  const outcome = await submitComparison(submission.request, comparisonId, request.signal)
  return Response.json(outcome)
}

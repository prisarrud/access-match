import type { ComparisonRequest, ComparisonSubmission } from '../../types'

export function readComparisonSubmission(
  propertyIds: ComparisonRequest['propertyIds'],
  params: Record<string, string | string[] | undefined>,
): ComparisonSubmission {
  const values = {
    stepFree: params.degraus === '1',
    ramp: params.rampa === '1',
    width: typeof params.largura === 'string' ? params.largura : '',
  }

  if (params.criterios !== '1') {
    return { status: 'idle', values: { stepFree: false, ramp: false, width: '' } }
  }

  const width = values.width.trim()
  const minimumClearWidthCm = width === '' ? null : Number(width.replace(',', '.'))

  if (
    Array.isArray(params.largura)
    || (minimumClearWidthCm !== null && (
      !/^[+-]?(?:\d+(?:[.,]\d*)?|[.,]\d+)$/.test(width)
      || !Number.isFinite(minimumClearWidthCm)
      || minimumClearWidthCm <= 0
    ))
  ) {
    return {
      status: 'invalid',
      values,
      errors: { width: 'Informe uma largura em centímetros com um número maior que zero.' },
    }
  }

  if (!values.stepFree && !values.ramp && minimumClearWidthCm === null) {
    return {
      status: 'invalid',
      values,
      errors: { criteria: 'Escolha pelo menos um critério ou informe a largura mínima.' },
    }
  }

  return {
    status: 'valid',
    values,
    request: { propertyIds, criteria: { stepFree: values.stepFree, ramp: values.ramp, minimumClearWidthCm } },
  }
}

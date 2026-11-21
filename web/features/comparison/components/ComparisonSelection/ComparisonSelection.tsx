import { Suspense } from 'react'
import {
  hasTwoPropertyIds, loadProperties, PropertyComparison, propertyQueryParam,
} from '@/features/property-access-comparison'
import { readComparisonSubmission } from '../../utils'
import { ComparisonCriteriaForm } from '../ComparisonCriteriaForm'
import { ComparisonResults } from '../ComparisonResults'

type ComparisonSelectionProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export async function ComparisonSelection({ searchParams }: ComparisonSelectionProps) {
  const params = await searchParams
  const ids = params[propertyQueryParam]

  if (!hasTwoPropertyIds(ids)) {
    return <p className='notice'>Selecione dois imóveis no catálogo para comparar.</p>
  }

  if (ids[0] === ids[1]) {
    return <p className='notice'>Selecione dois imóveis diferentes para comparar.</p>
  }

  const properties = await loadProperties()

  if (properties === null) {
    return (
      <p className='notice'>
        Não foi possível consultar o catálogo. Recarregue a página para tentar novamente.
      </p>
    )
  }

  const first = properties.find((property) => property.id === ids[0])
  const second = properties.find((property) => property.id === ids[1])

  if (!first || !second) {
    return <p className='notice'>Um ou mais imóveis da seleção não estão no catálogo.</p>
  }

  const submission = readComparisonSubmission(ids, params)
  const comparisonId = params.novaAnalise === '1' || params.comparacao === undefined
    ? undefined
    : typeof params.comparacao === 'string' ? params.comparacao : ''

  return (
    <>
      <PropertyComparison properties={[first, second]} />

      <ComparisonCriteriaForm propertyIds={ids} submission={submission} comparisonId={comparisonId} />

      {submission.status === 'valid' && (
        <Suspense fallback={
          <p className='notice' role='status'>
            {comparisonId === undefined ? 'Analisando as fontes da comparação…' : 'Atualizando a comparação…'}
          </p>
        }>
          <ComparisonResults submission={submission} comparisonId={comparisonId} />
        </Suspense>
      )}
    </>
  )
}

import { redirect } from 'next/navigation'
import { propertyQueryParam, type PropertySummary } from '@/features/property-access-comparison'
import { submitComparison } from '../../services'
import type { ComparisonSubmission } from '../../types'
import { ComparisonTable } from '../ComparisonTable'
import { ComparisonAnnouncement } from './ComparisonAnnouncement'
import styles from './ComparisonResults.module.css'

type ComparisonResultsProps = {
  submission: Extract<ComparisonSubmission, { status: 'valid' }>
  comparisonId?: string
  catalogProperties: PropertySummary[]
}

function RetryAnalysisButton() {
  return (
    <button type='submit' form='criterios' name='novaAnalise' value='1' className='button button-secondary'>
      Executar nova análise
    </button>
  )
}

export async function ComparisonResults({ submission, comparisonId, catalogProperties }: ComparisonResultsProps) {
  const outcome = await submitComparison(submission.request, comparisonId)
  if (outcome.status === 'unavailable') {
    return (
      <div className='notice'>
        <p role='alert'>A análise anterior expirou ou não está disponível para estes imóveis.</p>

        <RetryAnalysisButton />
      </div>
    )
  }

  if (outcome.status === 'error') {
    return (
      <p className='notice' role='alert'>
        Não foi possível concluir a comparação. Confirme os critérios novamente para tentar outra vez.
      </p>
    )
  }

  const { comparison } = outcome

  if (comparisonId === undefined) {
    const { propertyIds, criteria } = submission.request

    const params = new URLSearchParams({
      comparacao: comparison.comparisonId, criterios: '1', largura: submission.values.width,
    })

    for (const id of propertyIds) params.append(propertyQueryParam, id)

    if (criteria.stepFree) params.set('degraus', '1')

    if (criteria.ramp) params.set('rampa', '1')

    redirect(`/comparar?${params}#criterios`)
  }

  const canRetryWidth = comparison.properties.some((property) => (
    property.results.some((result) => result.criterion === 'largura' && result.status === 'a_confirmar') &&
    property.issues.some((issue) => issue.criterion === 'largura')
  ))

  return (
    <section className={styles.results} aria-labelledby='comparison-result-title'>
      <h2 id='comparison-result-title'>Resultado da comparação</h2>

      <ComparisonAnnouncement />

      <ComparisonTable
        criteria={submission.request.criteria}
        properties={comparison.properties}
        catalogProperties={catalogProperties}
      />

      {canRetryWidth && <RetryAnalysisButton />}
    </section>
  )
}

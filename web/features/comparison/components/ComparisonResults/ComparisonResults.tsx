import ui from '@/ui/shared.module.css'
import type { PropertySummary } from '@/features/property-access-comparison'
import type { ComparisonResponse, ComparisonSubmission } from '../../types'
import { AdvertiserQuestions } from '../AdvertiserQuestions'
import { ComparisonCriterionGroups } from '../ComparisonCriterionGroups'
import styles from './ComparisonResults.module.css'

type ComparisonResultsProps = {
  submission: Extract<ComparisonSubmission, { status: 'valid' }>
  comparison: ComparisonResponse
  catalogProperties: PropertySummary[]
}

function RetryAnalysisButton() {
  return (
    <button type='submit' form='criterios' name='novaAnalise' value='1' className={`${ui.button} ${ui.secondary}`}>
      Executar nova análise
    </button>
  )
}

export function ComparisonResults({ submission, comparison, catalogProperties }: ComparisonResultsProps) {
  const canRetryWidth = comparison.properties.some((property) => (
    property.results.some((result) => result.criterion === 'largura' && result.status === 'a_confirmar') &&
    property.issues.some((issue) => issue.criterion === 'largura')
  ))
  const propertiesWithPending = comparison.properties.filter((property) => (
    property.results.some((result) => result.toConfirm.length > 0)
  ))

  return (
    <section className={styles.results} aria-labelledby='comparison-result-title'>
      <h2 id='comparison-result-title'>Resultado da comparação</h2>

      <ComparisonCriterionGroups
        criteria={submission.request.criteria}
        properties={comparison.properties}
        catalogProperties={catalogProperties}
      />

      {canRetryWidth && <RetryAnalysisButton />}

      {propertiesWithPending.length > 0 && (
        <section className={styles.questions} aria-labelledby='comparison-questions-title'>
          <h3 id='comparison-questions-title'>Perguntas ao anunciante</h3>
          {propertiesWithPending.map((property) => (
            <AdvertiserQuestions
              key={JSON.stringify([comparison.comparisonId, submission.request, property.propertyId])}
              comparisonId={comparison.comparisonId}
              request={submission.request}
              propertyId={property.propertyId}
              propertyTitle={property.title}
            />
          ))}
        </section>
      )}
    </section>
  )
}

import { redirect } from 'next/navigation'
import { propertyQueryParam } from '@/features/property-access-comparison'
import { submitComparison } from '../../services'
import type { ComparisonSubmission, CriterionResult } from '../../types'
import styles from './ComparisonResults.module.css'

const criterionLabels = {
  degraus: 'Acesso sem degraus',
  rampas: 'Presença de rampa',
  largura: 'Largura livre mínima',
} satisfies Record<CriterionResult['criterion'], string>

const statusLabels = {
  atende: 'Atende',
  nao_atende: 'Não atende',
  a_confirmar: 'A confirmar',
} satisfies Record<CriterionResult['status'], string>

const documentLabels = {
  memorial: 'Memorial descritivo',
  vistoria: 'Ficha de vistoria',
}

type ComparisonResultsProps = {
  submission: Extract<ComparisonSubmission, { status: 'valid' }>
  comparisonId?: string
}

export async function ComparisonResults({ submission, comparisonId }: ComparisonResultsProps) {
  const outcome = await submitComparison(submission.request, comparisonId)
  if (outcome.status === 'unavailable') {
    return (
      <div className='notice'>
        <p role='alert'>A análise anterior expirou ou não está disponível para estes imóveis.</p>

        <button type='submit' form='criterios' name='novaAnalise' value='1' className='button button-secondary'>
          Executar nova análise
        </button>
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

  return (
    <section className={styles.results} aria-labelledby='comparison-result-title'>
      <h2 id='comparison-result-title'>Resultado da comparação</h2>

      {comparison.properties.map((property) => {
        const references = new Map([
          ...property.evidence.textSources.map((source) => {
            const title = source.document_type ? documentLabels[source.document_type] : 'Anúncio'
            return [source.source_id, source.page === null ? title : `${title}, página ${source.page}`] as const
          }),
          ...property.evidence.visual.map((photo) => (
            [photo.photo_id, `Foto: ${photo.source_path.split('/').at(-1)}`] as const
          )),
        ])

        return (
          <article className={styles.property} key={property.propertyId}>
            <h3>{property.title}</h3>

            <ul className={styles.criteria}>
              {property.results.map((result) => (
                <li key={result.criterion}>
                  <h4>{criterionLabels[result.criterion]}</h4>

                  <p><strong>{statusLabels[result.status]}</strong>{result.divergence && ' · Divergência entre fontes'}</p>

                  <p>{result.justification}</p>

                  {result.referenceIds.length > 0 && (
                    <p className={styles.detail}>
                      Fontes: {result.referenceIds.map((id) => references.get(id) ?? id).join(' · ')}
                    </p>
                  )}
                </li>
              ))}
            </ul>

            {property.issues.length > 0 && (
              <div role='status'>
                <h4>Análises incompletas</h4>

                <ul>
                  {property.issues.map((issue, index) => (
                    <li key={index}>
                      {issue.criterion && `${criterionLabels[issue.criterion]}: `}

                      {issue.message}

                      {issue.photoId && ` ${references.get(issue.photoId) ?? issue.photoId}.`}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </article>
        )
      })}
    </section>
  )
}

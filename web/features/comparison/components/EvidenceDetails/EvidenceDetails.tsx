import type { PropertySummary } from '@/features/property-access-comparison'
import type { ComparisonResponse, CriterionResult } from '../../types'
import { EvidencePhoto } from './EvidencePhoto'
import styles from './EvidenceDetails.module.css'

type PropertyResult = ComparisonResponse['properties'][number]
type Photo = PropertyResult['evidence']['visual'][number]

const documentTypes = {
  memorial: 'Memorial de projeto',
  vistoria: 'Registro de vistoria',
}

const locations = {
  calcada: 'na calçada',
  portao: 'no portão',
  trajeto: 'no trajeto',
  patamar: 'no patamar',
  porta_entrada: 'na porta de entrada',
  entre_calcada_e_patamar: 'entre a calçada e o patamar',
  entre_trajeto_e_patamar: 'entre o trajeto e o patamar',
}

function describePhoto(photo: Photo, criterion: CriterionResult['criterion']) {
  const element = criterion === 'degraus' ? 'degrau' : criterion === 'rampas' ? 'rampa' : null
  const observations = photo.observations.filter((observation) => observation.element === element)
  if (observations.length > 0) {
    return observations.map(({ element, location }) => (
      `${element === 'degrau' ? 'Degrau observado' : 'Rampa observada'} ${location ? locations[location] : 'no trecho fotografado'}.`
    ))
  }

  if (photo.assessments.some((assessment) => assessment.element === element && assessment.state === 'not_observed')) {
    return [element === 'degrau'
      ? 'Nenhum degrau foi observado no trecho fotografado.'
      : 'Nenhuma rampa foi observada no trecho fotografado.']
  }

  return []
}

export function EvidenceDetails({ result, property, catalogProperty, criterionLabel }: {
  result: CriterionResult
  property: PropertyResult
  catalogProperty?: PropertySummary
  criterionLabel: string
}) {
  const { evidence } = property
  const context = `${property.title} · ${criterionLabel}`

  return (
    <details className={styles.details}>
      <summary className={styles.summary} aria-label={`Ver evidências de ${context}`}>Ver evidências</summary>
      <p className={styles.context}>{context}</p>
      <ul className={styles.sources}>
        {result.referenceIds.map((id) => {
          const source = evidence.textSources.find((item) => item.source_id === id && item.property_id === property.propertyId)
          if (source) {
            const quotes = evidence.textual
              .filter((item) => item.source_id === id && item.criterion === result.criterion)
              .map((item) => item.quote)
            const type = source.document_type && documentTypes[source.document_type]
            const document = catalogProperty?.documents.find((item) => item.id === source.document_id)
            const page = source.page === null ? '' : `Página ${source.page}`
            const href = document?.url && `${document.url}${source.page === null ? '' : `#page=${source.page}`}`

            return (
              <li key={id} data-source-id={id} className={styles.source}>
                <p><strong>{document?.title ?? type ?? 'Anúncio'}</strong></p>
                {type && <p className={styles.metadata}>{[type, page].filter(Boolean).join(' · ')}</p>}
                {Array.from(new Set(quotes.length > 0 ? quotes : [source.text]), (quote) => (
                  <blockquote key={quote}>{quote}</blockquote>
                ))}
                {type && (href ? (
                  <p>
                    <a href={href} target='_blank' rel='noopener' aria-label={`Abrir PDF de ${document?.title} (nova aba)`}>
                      Abrir PDF (nova aba)
                    </a>
                  </p>
                ) : <p>PDF indisponível.</p>)}
              </li>
            )
          }

          const photo = evidence.visual.find((item) => item.photo_id === id)
          if (photo) {
            const media = catalogProperty?.photos.find((item) => item.id === id)
            return (
              <li key={id} data-source-id={id} className={styles.source}>
                <p><strong>Foto do acesso</strong></p>
                <EvidencePhoto url={media?.url ?? null} alt={media?.alt ?? ''} />
                {describePhoto(photo, result.criterion).map((description) => (
                  <p key={description}>{description}</p>
                ))}
              </li>
            )
          }

          return <li key={id} data-source-id={id} className={styles.source}>Fonte indisponível ({id}).</li>
        })}
      </ul>
    </details>
  )
}

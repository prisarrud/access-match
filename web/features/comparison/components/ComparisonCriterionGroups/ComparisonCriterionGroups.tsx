import type { PropertySummary } from '@/features/property-access-comparison'
import type { ComparisonCriteria, ComparisonResponse, CriterionResult } from '../../types'
import { EvidenceDetails } from '../EvidenceDetails'
import styles from './ComparisonCriterionGroups.module.css'

type Criterion = CriterionResult['criterion']
type PropertyResult = ComparisonResponse['properties'][number]

const criterionLabels = {
  degraus: 'Acesso sem degraus',
  rampas: 'Presença de rampa',
  largura: 'Largura livre mínima',
} satisfies Record<Criterion, string>

const statusLabels = {
  atende: 'Atende',
  nao_atende: 'Não atende',
  a_confirmar: 'A confirmar',
} satisfies Record<CriterionResult['status'], string>

const widthStatusLabels = {
  ...statusLabels,
  atende: 'Atende à medida solicitada',
  nao_atende: 'Abaixo da medida solicitada',
}

const confirmations = {
  route_continuity: 'Continuidade do trajeto da calçada até a porta de entrada.',
  alternate_access: 'Existência de outro acesso sem degraus.',
  ramp_slope: 'Inclinação da rampa.',
  ramp_width: 'Largura livre da rampa.',
  ramp_continuity: 'Ligação da rampa com o restante do trajeto.',
  current_entrance_width: 'Medida atual do vão livre da porta de entrada.',
} satisfies Record<CriterionResult['toConfirm'][number], string>

function AnalysisIssues({
  issues, photos,
}: { issues: PropertyResult['issues'], photos: Map<string, string> }) {
  return (
    <div className={styles.issues}>
      <p><strong>Falha na análise</strong></p>
      <ul>
        {issues.map((issue, index) => (
          <li key={index}>
            {issue.message}
            {issue.photoId && ` ${photos.get(issue.photoId) ?? issue.photoId}.`}
          </li>
        ))}
      </ul>
    </div>
  )
}

function PropertyResultCard({
  criterion, property, photos, catalogProperty, headingId,
}: { criterion: Criterion, property: PropertyResult, photos: Map<string, string>, catalogProperty?: PropertySummary, headingId: string }) {
  const result = property.results.find((item) => item.criterion === criterion)
  const issues = property.issues.filter((issue) => issue.criterion === criterion)
  const labels = criterion === 'largura' ? widthStatusLabels : statusLabels

  return (
    <article className={styles.card} aria-labelledby={`comparison-criterion-${criterion} ${headingId}`}>
      <h4 id={headingId}>{property.title}</h4>
      {result && (
        <>
          <div className={styles.statuses}>
            <strong className={styles.status} data-status={result.status}>{labels[result.status]}</strong>
            {result.divergence && <strong className={styles.conflict}>Informações em conflito</strong>}
          </div>

          <p>{result.justification}</p>

          {result.toConfirm.length > 0 && (
            <div className={styles.pending}>
              <p><strong>O que falta confirmar</strong></p>
              <ul>
                {result.toConfirm.map((item) => <li key={item}>{confirmations[item]}</li>)}
              </ul>
            </div>
          )}
        </>
      )}

      {issues.length > 0 && <AnalysisIssues issues={issues} photos={photos} />}
      {!result && issues.length === 0 && <p>Resultado indisponível para este critério.</p>}
      {result && result.referenceIds.length > 0 && (
        <footer className={styles.evidence}>
          <EvidenceDetails
            result={result}
            property={property}
            catalogProperty={catalogProperty}
            criterionLabel={criterionLabels[criterion]}
          />
        </footer>
      )}
    </article>
  )
}

export function ComparisonCriterionGroups({
  criteria, properties, catalogProperties,
}: { criteria: ComparisonCriteria, properties: ComparisonResponse['properties'], catalogProperties: PropertySummary[] }) {
  const requestedCriteria: Criterion[] = []
  if (criteria.stepFree) requestedCriteria.push('degraus')
  if (criteria.ramp) requestedCriteria.push('rampas')
  if (criteria.minimumClearWidthCm !== null) requestedCriteria.push('largura')

  const propertyResults = properties.map((property) => ({
    property,
    catalogProperty: catalogProperties.find((item) => item.id === property.propertyId),
    photos: new Map(property.evidence.visual.map((photo) => [photo.photo_id, photo.source_path.split('/').at(-1) ?? photo.photo_id])),
    generalIssues: property.issues.filter((issue) => issue.criterion === null),
  }))

  return (
    <>
      {requestedCriteria.map((criterion) => (
        <section key={criterion} className={styles.group} aria-labelledby={`comparison-criterion-${criterion}`}>
          <h3 id={`comparison-criterion-${criterion}`} className={styles.heading}>
            {criterionLabels[criterion]}
            {criterion === 'largura' && (
              <span className={styles.minimumWidth}>
                {' · '}{String(criteria.minimumClearWidthCm).replace('.', ',')} cm
              </span>
            )}
          </h3>

          <div className={styles.grid}>
            {propertyResults.map(({ property, catalogProperty, photos }, index) => (
              <PropertyResultCard
                key={property.propertyId}
                criterion={criterion}
                property={property}
                catalogProperty={catalogProperty}
                photos={photos}
                headingId={`comparison-property-${criterion}-${index}`}
              />
            ))}
          </div>
        </section>
      ))}

      {propertyResults.map(({ property, photos, generalIssues }) => (
        generalIssues.length > 0 && (
          <div key={property.propertyId} className={styles.propertyIssues}>
            <h3>{property.title}</h3>
            <AnalysisIssues issues={generalIssues} photos={photos} />
          </div>
        )
      ))}
    </>
  )
}

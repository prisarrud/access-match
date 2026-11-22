import type { PropertySummary } from '@/features/property-access-comparison'
import type { ComparisonCriteria, ComparisonResponse, CriterionResult } from '../../types'
import { EvidenceDetails } from '../EvidenceDetails'
import styles from './ComparisonTable.module.css'

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

function ComparisonCell({
  criterion, property, photos, catalogProperty,
}: { criterion: Criterion, property: PropertyResult, photos: Map<string, string>, catalogProperty?: PropertySummary }) {
  const result = property.results.find((item) => item.criterion === criterion)
  const issues = property.issues.filter((issue) => issue.criterion === criterion)
  const labels = criterion === 'largura' ? widthStatusLabels : statusLabels

  return (
    <td>
      {result && (
        <>
          <div className={styles.statuses}>
            <strong className={styles.status} data-status={result.status}>{labels[result.status]}</strong>
            {result.divergence && <strong className={styles.conflict}>Informações em conflito</strong>}
          </div>

          <p>{result.justification}</p>

          {(result.referenceIds.length > 0 || result.toConfirm.length > 0) && (
            <EvidenceDetails
              result={result}
              property={property}
              catalogProperty={catalogProperty}
              criterionLabel={criterionLabels[criterion]}
            />
          )}
        </>
      )}

      {issues.length > 0 && <AnalysisIssues issues={issues} photos={photos} />}
      {!result && issues.length === 0 && <p>Resultado indisponível para este critério.</p>}
    </td>
  )
}

export function ComparisonTable({
  criteria, properties, catalogProperties,
}: { criteria: ComparisonCriteria, properties: ComparisonResponse['properties'], catalogProperties: PropertySummary[] }) {
  const rows: Criterion[] = []
  if (criteria.stepFree) rows.push('degraus')
  if (criteria.ramp) rows.push('rampas')
  if (criteria.minimumClearWidthCm !== null) rows.push('largura')

  const columns = properties.map((property) => ({
    property,
    catalogProperty: catalogProperties.find((item) => item.id === property.propertyId),
    photos: new Map(property.evidence.visual.map((photo) => [photo.photo_id, photo.source_path.split('/').at(-1) ?? photo.photo_id])),
    generalIssues: property.issues.filter((issue) => issue.criterion === null),
  }))

  return (
    <>
      <p className={styles.scrollHint}>Deslize ou use as setas na tabela para ver os dois imóveis.</p>

      <div className={styles.scrollArea} role='region' aria-label='Tabela de resultados' tabIndex={0}>
        <table className={styles.table} aria-labelledby='comparison-result-title'>
          <thead>
            <tr>
              <th scope='col'>Critério</th>
              {columns.map(({ property }) => (
                <th key={property.propertyId} scope='col'>{property.title}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((criterion) => (
              <tr key={criterion}>
                <th scope='row'>
                  {criterionLabels[criterion]}
                  {criterion === 'largura' && (
                    <span className={styles.minimumWidth}>
                      {String(criteria.minimumClearWidthCm).replace('.', ',')} cm
                    </span>
                  )}
                </th>
                {columns.map(({ property, catalogProperty, photos }) => (
                  <ComparisonCell
                    key={property.propertyId}
                    criterion={criterion}
                    property={property}
                    catalogProperty={catalogProperty}
                    photos={photos}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {columns.map(({ property, photos, generalIssues }) => (
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

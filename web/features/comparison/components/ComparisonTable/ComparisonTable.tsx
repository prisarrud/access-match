import type { ComparisonCriteria, ComparisonResponse, CriterionResult } from '../../types'
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

const documentLabels = {
  memorial: 'Memorial descritivo',
  vistoria: 'Ficha de vistoria',
}

function describeSources(evidence: PropertyResult['evidence']) {
  return new Map([
    ...evidence.textSources.map((source) => {
      const title = source.document_type ? documentLabels[source.document_type] : 'Anúncio'
      return [source.source_id, source.page === null ? title : `${title}, página ${source.page}`] as const
    }),
    ...evidence.visual.map((photo) => (
      [photo.photo_id, `Foto: ${photo.source_path.split('/').at(-1)}`] as const
    )),
  ])
}

function AnalysisIssues({
  issues, sources,
}: { issues: PropertyResult['issues'], sources: Map<string, string> }) {
  return (
    <div className={styles.issues}>
      <p><strong>Falha na análise</strong></p>
      <ul>
        {issues.map((issue, index) => (
          <li key={index}>
            {issue.message}
            {issue.photoId && ` ${sources.get(issue.photoId) ?? issue.photoId}.`}
          </li>
        ))}
      </ul>
    </div>
  )
}

function ComparisonCell({
  criterion, property, sources,
}: { criterion: Criterion, property: PropertyResult, sources: Map<string, string> }) {
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

          {result.referenceIds.length > 0 && (
            <div className={styles.sources}>
              <p>Fontes</p>
              <ul>
                {result.referenceIds.map((id) => (
                  <li key={id} data-source-id={id}>{sources.get(id) ?? id}</li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      {issues.length > 0 && <AnalysisIssues issues={issues} sources={sources} />}
      {!result && issues.length === 0 && <p>Resultado indisponível para este critério.</p>}
    </td>
  )
}

export function ComparisonTable({
  criteria, properties,
}: { criteria: ComparisonCriteria, properties: ComparisonResponse['properties'] }) {
  const rows: Criterion[] = []
  if (criteria.stepFree) rows.push('degraus')
  if (criteria.ramp) rows.push('rampas')
  if (criteria.minimumClearWidthCm !== null) rows.push('largura')

  const columns = properties.map((property) => ({
    property,
    sources: describeSources(property.evidence),
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
                {columns.map(({ property, sources }) => (
                  <ComparisonCell key={property.propertyId} criterion={criterion} property={property} sources={sources} />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {columns.map(({ property, sources, generalIssues }) => (
        generalIssues.length > 0 && (
          <div key={property.propertyId} className={styles.propertyIssues}>
            <h3>{property.title}</h3>
            <AnalysisIssues issues={generalIssues} sources={sources} />
          </div>
        )
      ))}
    </>
  )
}

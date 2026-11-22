export type CriterionResult = {
  criterion: 'degraus' | 'rampas' | 'largura'
  status: 'atende' | 'nao_atende' | 'a_confirmar'
  justification: string
  referenceIds: string[]
  divergence: boolean
  toConfirm: (
    'route_continuity' | 'alternate_access' | 'ramp_slope' | 'ramp_width' | 'ramp_continuity' | 'current_entrance_width'
  )[]
}

type SourceReference = {
  source_id: string
  property_id: string
  document_id: string | null
  document_type: 'memorial' | 'vistoria' | null
  page: number | null
  text: string
}

type PhotoObservation = {
  element: 'degrau' | 'rampa'
  location: 'calcada' | 'portao' | 'trajeto' | 'patamar' | 'porta_entrada'
    | 'entre_calcada_e_patamar' | 'entre_trajeto_e_patamar' | null
}

export type ComparisonResponse = {
  comparisonId: string
  properties: {
    propertyId: string
    title: string
    results: CriterionResult[]
    evidence: {
      textSources: SourceReference[]
      textual: { source_id: string, criterion: CriterionResult['criterion'], quote: string }[]
      visual: {
        photo_id: string
        source_path: string
        observations: PhotoObservation[]
        assessments: { element: PhotoObservation['element'], state: 'observed' | 'not_observed' | 'not_assessable' }[]
      }[]
    }
    issues: { message: string, criterion: CriterionResult['criterion'] | null, photoId: string | null }[]
  }[]
}

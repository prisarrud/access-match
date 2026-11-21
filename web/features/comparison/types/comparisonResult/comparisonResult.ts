export type CriterionResult = {
  criterion: 'degraus' | 'rampas' | 'largura'
  status: 'atende' | 'nao_atende' | 'a_confirmar'
  justification: string
  referenceIds: string[]
  divergence: boolean
}

type SourceReference = {
  source_id: string
  document_type: 'memorial' | 'vistoria' | null
  page: number | null
}

export type ComparisonResponse = {
  properties: {
    propertyId: string
    title: string
    results: CriterionResult[]
    evidence: {
      textSources: SourceReference[]
      visual: { photo_id: string, source_path: string }[]
    }
    issues: { message: string, criterion: CriterionResult['criterion'] | null, photoId: string | null }[]
  }[]
}

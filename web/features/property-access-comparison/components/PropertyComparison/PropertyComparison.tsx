import type { PropertySummary } from '../../types'
import { PropertyCard } from '../PropertyCard'

type ComparisonProps = {
  properties: [PropertySummary, PropertySummary]
}

export function PropertyComparison({ properties }: ComparisonProps) {
  return (
    <ul className='property-grid' role='list' aria-label='Imóveis selecionados'>
      {properties.map((property) => (
        <li key={property.id}>
          <PropertyCard property={property} />
        </li>
      ))}
    </ul>
  )
}

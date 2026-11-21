import { propertyQueryParam } from '../../constants'
import { loadProperties } from '../../services'
import { hasTwoPropertyIds } from '../../utils'
import { PropertyCard } from '../PropertyCard'

type ComparisonProps = {
  searchParams: Promise<Record<string, string | string[] | undefined>>
}

export async function PropertyComparison({ searchParams }: ComparisonProps) {
  const ids = (await searchParams)[propertyQueryParam]

  if (!hasTwoPropertyIds(ids)) {
    return <p className='notice'>Selecione dois imóveis no catálogo para comparar.</p>
  }

  if (ids[0] === ids[1]) {
    return <p className='notice'>Selecione dois imóveis diferentes para comparar.</p>
  }

  const properties = await loadProperties()

  if (properties === null) {
    return (
      <p className='notice'>
        Não foi possível consultar o catálogo. Recarregue a página para tentar novamente.
      </p>
    )
  }

  const first = properties.find((property) => property.id === ids[0])
  const second = properties.find((property) => property.id === ids[1])

  if (!first || !second) {
    return <p className='notice'>Um ou mais imóveis da seleção não estão no catálogo.</p>
  }

  return (
    <ul className='property-grid' role='list' aria-label='Imóveis selecionados'>
      {[first, second].map((property) => (
        <li key={property.id}>
          <PropertyCard property={property} />
        </li>
      ))}
    </ul>
  )
}

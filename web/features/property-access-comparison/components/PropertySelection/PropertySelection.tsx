'use client'

import { propertyQueryParam, selectionLimit } from '../../constants'
import { usePropertySelection } from '../../hooks'
import type { PropertySummary } from '../../types'
import { PropertyCard } from '../PropertyCard'

export function PropertySelection({ properties }: { properties: PropertySummary[] }) {
  const { selectedIds, toggleProperty } = usePropertySelection()

  return (
    <form action='/comparar' method='get'>
      <ul className='content-container property-grid' role='list'>
        {properties.map((property) => {
          const selected = selectedIds.includes(property.id)
          const action = selected ? 'Remover da seleção' : 'Selecionar imóvel'

          return (
            <li key={property.id}>
              <PropertyCard
                property={property}
                selected={selected}
                heading='h3'
                action={
                  <button
                    type='button'
                    className='button button-secondary'
                    disabled={!selected && selectedIds.length === selectionLimit}
                    onClick={() => toggleProperty(property.id)}
                    aria-label={`${action}: ${property.title}`}
                  >
                    {action}
                  </button>
                }
              />
            </li>
          )
        })}
      </ul>

      {selectedIds.map((id) => (
        <input key={id} type='hidden' name={propertyQueryParam} value={id} />
      ))}

      <div className='selection-band'>
        <div className='content-container selection-bar'>
          <div className='selection-summary'>
            <div className='selection-meter' aria-hidden='true'>
              <span data-filled={selectedIds.length >= 1} />
              <span data-filled={selectedIds.length === selectionLimit} />
            </div>

            <p role='status'>
              <strong>{selectedIds.length} de {selectionLimit}</strong> imóveis selecionados
            </p>
          </div>
          <button
            type='submit'
            className='button button-primary'
            disabled={selectedIds.length !== selectionLimit}
          >
            Comparar imóveis
          </button>
        </div>
      </div>
    </form>
  )
}

'use client'

import ui from '@/ui/shared.module.css'
import styles from './PropertySelection.module.css'
import layout from '../PropertyGrid.module.css'
import { useSearchParams } from 'next/navigation'
import { useEffect, useRef, type SubmitEvent } from 'react'
import { propertyQueryParam, selectionLimit } from '../../constants'
import type { PropertySummary } from '../../types'
import { PropertyCard } from '../PropertyCard'

function PropertyInputs({ ids }: { ids: string[] }) {
  return ids.map((id) => <input key={id} type='hidden' name={propertyQueryParam} value={id} />)
}

function toggleProperty(ids: string[], id: string) {
  if (ids.includes(id)) return ids.filter((selected) => selected !== id)
  return ids.length < selectionLimit ? [...ids, id] : ids
}

export function PropertySelection({ properties }: { properties: PropertySummary[] }) {
  const params = useSearchParams()
  const propertyIds = new Set(properties.map((property) => property.id))
  const bandRef = useRef<HTMLDivElement>(null)
  const clearanceRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const band = bandRef.current
    const clearance = clearanceRef.current
    if (!band || !clearance) return

    const reserveSpace = () => {
      clearance.style.blockSize = `${band.getBoundingClientRect().height}px`
    }
    reserveSpace()
    const observer = new ResizeObserver(reserveSpace)
    observer.observe(band, { box: 'border-box' })
    return () => observer.disconnect()
  }, [])

  function readSelection(query: Pick<URLSearchParams, 'getAll'>) {
    return [...new Set(query.getAll(propertyQueryParam))]
      .filter((id) => propertyIds.has(id))
      .slice(0, selectionLimit)
  }

  const selectedIds = readSelection(params)

  function updateSelection(event: SubmitEvent<HTMLFormElement>, id: string) {
    event.preventDefault()

    const url = new URL(window.location.href)
    const nextIds = toggleProperty(readSelection(url.searchParams), id)
    url.searchParams.delete(propertyQueryParam)
    for (const selected of nextIds) url.searchParams.append(propertyQueryParam, selected)
    window.history.replaceState(null, '', url)
  }

  return (
    <>
      <ul className={`${ui.container} ${layout.grid} ${styles.catalogGrid}`} role='list'>
        {properties.map((property) => {
          const selected = selectedIds.includes(property.id)
          const action = selected ? 'Remover da seleção' : 'Selecionar imóvel'
          const controlId = `select-property-${encodeURIComponent(property.id)}`
          const nextIds = toggleProperty(selectedIds, property.id)

          return (
            <li key={property.id}>
              <PropertyCard
                property={property}
                selected={selected}
                heading='h3'
                action={
                  <form
                    action={`/#${encodeURIComponent(controlId)}`}
                    method='get'
                    onSubmit={(event) => updateSelection(event, property.id)}
                  >
                    <PropertyInputs ids={nextIds} />
                    <button
                      id={controlId}
                      type='submit'
                      className={`${ui.button} ${ui.outline}`}
                      disabled={!selected && selectedIds.length === selectionLimit}
                      aria-label={`${action}: ${property.title}`}
                    >
                      {action}
                    </button>
                  </form>
                }
              />
            </li>
          )
        })}
      </ul>

      <div ref={clearanceRef} className={styles.clearance} aria-hidden='true' />

      <div ref={bandRef} className={styles.band}>
        <form action='/comparar' method='get' className={`${ui.container} ${styles.bar}`}>
          <PropertyInputs ids={selectedIds} />
          <div className={styles.summary}>
            <div className={styles.meter} aria-hidden='true'>
              <span data-filled={selectedIds.length >= 1} />
              <span data-filled={selectedIds.length === selectionLimit} />
            </div>

            <p role='status'>
              <strong>{selectedIds.length} de {selectionLimit}</strong> imóveis selecionados
            </p>
          </div>
          <button
            type='submit'
            className={`${ui.button} ${ui.primary}`}
            disabled={selectedIds.length !== selectionLimit}
          >
            Comparar imóveis
          </button>
        </form>
      </div>
    </>
  )
}

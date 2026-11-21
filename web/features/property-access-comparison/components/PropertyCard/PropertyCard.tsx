import Image from 'next/image'
import type { ReactNode } from 'react'
import type { PropertySummary } from '../../types'

type PropertyCardProps = {
  property: PropertySummary
  selected?: boolean
  action?: ReactNode
  heading?: 'h2' | 'h3'
}

export function PropertyCard({
  property,
  selected,
  action,
  heading: Heading = 'h2',
}: PropertyCardProps) {
  return (
    <div className='property-card' data-selected={selected}>
      {property.cover && (
        <div className='property-cover'>
          <Image src={property.cover.url} alt={property.cover.alt} fill unoptimized />
        </div>
      )}

      <div className='property-body'>
        <Heading className='property-title'>{property.title}</Heading>

        <p className='property-description'>{property.description}</p>

        {action && <div className='property-action'>{action}</div>}
      </div>
    </div>
  )
}

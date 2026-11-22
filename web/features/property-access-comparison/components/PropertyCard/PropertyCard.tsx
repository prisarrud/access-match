import Image from 'next/image'
import type { ReactNode } from 'react'
import type { PropertySummary } from '../../types'

import styles from './PropertyCard.module.css'

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
    <div className={action ? `${styles.card} ${styles.catalogCard}` : styles.card} data-selected={selected}>
      <div className={styles.cover}>
        {property.cover ? (
          <Image src={property.cover.url} alt={property.cover.alt} fill unoptimized />
        ) : <span className={styles.placeholder}>Foto indisponível</span>}
      </div>
      <div className={styles.body}>
        <Heading className={styles.title}>{property.title}</Heading>
        <p className={styles.description}>{property.description}</p>
        {action && <div className={styles.action}>{action}</div>}
      </div>
    </div>
  )
}

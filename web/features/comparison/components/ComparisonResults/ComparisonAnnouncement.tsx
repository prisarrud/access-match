'use client'

import { useEffect, useState } from 'react'
import styles from './ComparisonResults.module.css'

export function ComparisonAnnouncement() {
  const [message, setMessage] = useState('')

  useEffect(() => {
    let frame = requestAnimationFrame(() => {
      frame = requestAnimationFrame(() => setMessage('Comparação atualizada.'))
    })

    return () => cancelAnimationFrame(frame)
  }, [])

  return <p className={styles.announcement} role='status' aria-live='polite'>{message}</p>
}

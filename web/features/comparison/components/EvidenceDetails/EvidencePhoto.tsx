'use client'

import Image from 'next/image'
import { useState } from 'react'
import styles from './EvidenceDetails.module.css'

export function EvidencePhoto({ url, alt }: { url: string | null, alt: string }) {
  const [failed, setFailed] = useState(false)

  if (!url || failed) {
    return <p role='status'>Foto indisponível. {alt}</p>
  }

  return (
    <>
      <div className={styles.photo}>
        <Image src={url} alt={alt} fill unoptimized onError={() => setFailed(true)} />
      </div>
      <p><a href={url} target='_blank' rel='noopener'>Abrir foto em tamanho original (nova aba)</a></p>
    </>
  )
}

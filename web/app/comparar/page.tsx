import ui from '@/ui/shared.module.css'
import styles from './page.module.css'
import type { Metadata } from 'next'
import Link from 'next/link'
import { Suspense } from 'react'
import { ComparisonSelection } from '@/features/comparison'

export const metadata: Metadata = {
  title: 'Comparar imóveis | AccessMatch',
}

export default function ComparePage({ searchParams }: PageProps<'/comparar'>) {
  return (
    <main className={styles.page}>
      <div className={styles.heading}>
        <Link href='/' className={styles.back}>Alterar imóveis selecionados</Link>

        <h1>Comparar imóveis</h1>
      </div>

      <Suspense fallback={<p className={ui.notice} role='status'>Carregando seleção…</p>}>
        <ComparisonSelection searchParams={searchParams} />
      </Suspense>
    </main>
  )
}

import type { Metadata } from 'next'
import Link from 'next/link'
import { Suspense } from 'react'
import { ComparisonSelection } from '@/features/comparison'

export const metadata: Metadata = {
  title: 'Comparar imóveis | AccessMatch',
}

export default function ComparePage({ searchParams }: PageProps<'/comparar'>) {
  return (
    <main className='page'>
      <div className='page-heading'>
        <Link href='/' className='back-link'>Alterar imóveis selecionados</Link>

        <h1>Comparar imóveis</h1>
      </div>

      <Suspense fallback={<p className='notice' role='status'>Carregando seleção…</p>}>
        <ComparisonSelection searchParams={searchParams} />
      </Suspense>
    </main>
  )
}

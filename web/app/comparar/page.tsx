import type { Metadata } from 'next'
import Link from 'next/link'
import { Suspense } from 'react'
import { PropertyComparison } from '@/features/property-access-comparison'

export const metadata: Metadata = {
  title: 'Comparar imóveis | AccessMatch',
}

export default function ComparePage({ searchParams }: PageProps<'/comparar'>) {
  return (
    <main className='page'>
      <div className='page-heading'>
        <Link href='/' className='back-link'>Voltar ao catálogo</Link>

        <h1>Comparar imóveis</h1>
      </div>

      <Suspense fallback={<p className='notice' role='status'>Carregando seleção…</p>}>
        <PropertyComparison searchParams={searchParams} />
      </Suspense>
    </main>
  )
}

import { Suspense } from 'react'
import { PropertyCatalog } from '@/features/property-access-comparison'

export default function Home() {
  return (
    <main>
      <header className='catalog-intro'>
        <div className='content-container'>
          <div className='catalog-intro-content'>
            <h1>Compare o acesso antes da visita.</h1>

            <p>
              Veja as fotos e os anúncios e escolha dois imóveis para comparar o
              percurso da calçada à porta.
            </p>
          </div>
        </div>
      </header>
      <section className='catalog-section' aria-labelledby='catalog-title'>
        <div className='content-container catalog-heading'>
          <h2 id='catalog-title'>Catálogo de imóveis</h2>

          <p>Dados fictícios</p>
        </div>

        <Suspense
          fallback={<p className='content-container notice' role='status'>Carregando imóveis…</p>}
        >
          <PropertyCatalog />
        </Suspense>
      </section>
    </main>
  )
}

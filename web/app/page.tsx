import ui from '@/ui/shared.module.css'
import styles from './page.module.css'
import { Suspense } from 'react'
import { PropertyCatalog } from '@/features/property-access-comparison'

export default function Home() {
  return (
    <main>
      <header className={styles.intro}>
        <div className={styles.introContainer}>
          <div className={styles.introContent}>
            <h1>Compare o acesso antes da visita.</h1>

            <p>
              Veja as fotos e os anúncios e escolha dois imóveis para comparar o
              percurso da calçada à porta.
            </p>
          </div>
        </div>
      </header>
      <section className={styles.catalog} aria-labelledby='catalog-title'>
        <div className={styles.heading}>
          <h2 id='catalog-title'>Catálogo de imóveis</h2>

          <p>Dados fictícios</p>
        </div>

        <Suspense
          fallback={<p className={ui.notice} role='status'>Carregando imóveis…</p>}
        >
          <PropertyCatalog />
        </Suspense>
      </section>
    </main>
  )
}

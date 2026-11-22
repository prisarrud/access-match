import { Roboto } from 'next/font/google'
import styles from './layout.module.css'
import type { Metadata } from 'next'
import Link from 'next/link'
import './globals.css'

const roboto = Roboto({ subsets: ['latin'], weight: ['400', '700'], display: 'swap' })

export const metadata: Metadata = {
  title: 'Catálogo de imóveis | AccessMatch',
  description: 'Escolha dois imóveis para comparar o acesso antes de marcar uma visita.',
}

export default function RootLayout({ children }: LayoutProps<'/'>) {
  return (
    <html lang='pt-BR'>
      <body className={roboto.className}>
        <header className={styles.header}>
          <div className={styles.inner}>
            <Link href='/' className={styles.brand} aria-label='AccessMatch, catálogo de imóveis'>
              <span className={styles.mark} aria-hidden='true' />

              <span>Access<span className={styles.accent}>Match</span></span>
            </Link>
          </div>
        </header>
        {children}
      </body>
    </html>
  )
}

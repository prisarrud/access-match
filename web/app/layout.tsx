import type { Metadata } from 'next'
import Link from 'next/link'
import './globals.css'

export const metadata: Metadata = {
  title: 'Catálogo de imóveis | AccessMatch',
  description: 'Escolha dois imóveis para comparar o acesso antes de marcar uma visita.',
}

export default function RootLayout({ children }: LayoutProps<'/'>) {
  return (
    <html lang='pt-BR'>
      <body>
        <header className='site-header'>
          <div className='site-header-inner'>
            <Link href='/' className='brand' aria-label='AccessMatch, catálogo de imóveis'>
              <span className='brand-mark' aria-hidden='true' />

              <span>Access<span className='brand-accent'>Match</span></span>
            </Link>
          </div>
        </header>
        {children}
      </body>
    </html>
  )
}

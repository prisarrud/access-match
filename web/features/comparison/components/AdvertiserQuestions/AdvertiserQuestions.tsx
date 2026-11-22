'use client'

import ui from '@/ui/shared.module.css'
import { useEffect, useId, useRef, useState } from 'react'
import { generateComparisonQuestions } from '../../services/generateComparisonQuestions/generateComparisonQuestions'
import type { ComparisonRequest } from '../../types'
import styles from './AdvertiserQuestions.module.css'

export function AdvertiserQuestions({ comparisonId, request, propertyId, propertyTitle }: {
  comparisonId: string
  request: ComparisonRequest
  propertyId: string
  propertyTitle: string
}) {
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error' | 'unavailable'>('idle')
  const [message, setMessage] = useState('')
  const [notice, setNotice] = useState('')
  const editor = useRef<HTMLTextAreaElement>(null)
  const generateButton = useRef<HTMLButtonElement>(null)
  const nextControl = useRef<HTMLButtonElement>(null)
  const restoreFocus = useRef(false)
  const headingId = useId()
  const editorId = useId()

  useEffect(() => {
    if (!restoreFocus.current) return
    restoreFocus.current = false
    if (status === 'ready') editor.current?.focus()
    if (status === 'unavailable') nextControl.current?.focus()
  }, [status])

  async function generate() {
    if (status === 'loading') return
    setStatus('loading')

    try {
      const result = await generateComparisonQuestions(comparisonId, request, propertyId)
      restoreFocus.current = document.activeElement === generateButton.current
      if (result.status !== 'success') {
        setStatus(result.status)
        return
      }

      const questions = result.questions.map(({ question }) => `- ${question}`).join('\n')
      setMessage(`Olá! Tenho algumas dúvidas sobre o acesso ao imóvel do anúncio “${propertyTitle}”.\n\n${questions}\n\nAgradeço pela ajuda!`)
      setNotice('Mensagem pronta para revisão.')
      setStatus('ready')
    } catch {
      setStatus('error')
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(message)
      setNotice('Mensagem copiada.')
    } catch {
      editor.current?.focus()
      editor.current?.select()
      setNotice('Texto selecionado. Use Ctrl+C ou ⌘C para copiar.')
    }
  }

  return (
    <section className={styles.property} aria-labelledby={headingId}>
      <h4 id={headingId}>{propertyTitle}</h4>

      {status !== 'ready' && status !== 'unavailable' && (
        <button
          ref={generateButton}
          type='button'
          className={`${ui.button} ${ui.outline}`}
          aria-disabled={status === 'loading'}
          onClick={generate}
        >
          Gerar perguntas ao anunciante
        </button>
      )}

      {status === 'error' && <p role='alert'>Não foi possível gerar as perguntas. Tente novamente.</p>}

      {status === 'unavailable' && (
        <>
          <p role='alert'>Esta comparação expirou. Execute uma nova análise para gerar perguntas atualizadas.</p>
          <button ref={nextControl} type='submit' form='criterios' name='novaAnalise' value='1' className={`${ui.button} ${ui.secondary}`}>
            Executar nova análise
          </button>
        </>
      )}

      {status === 'ready' && (
        <>
          <label htmlFor={editorId}>Mensagem para o anunciante</label>
          <textarea
            id={editorId}
            ref={editor}
            className={styles.message}
            rows={8}
            value={message}
            onChange={(event) => {
              setMessage(event.target.value)
              setNotice('')
            }}
          />
          <button type='button' className={`${ui.button} ${ui.secondary}`} disabled={!message.trim()} onClick={copy}>
            Copiar mensagem
          </button>
        </>
      )}

      <p role='status'>{status === 'loading' ? 'Gerando perguntas…' : notice}</p>
    </section>
  )
}

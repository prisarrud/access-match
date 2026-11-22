'use client'

import ui from '@/ui/shared.module.css'
import { useCallback, useEffect, useRef, useState, type SubmitEvent } from 'react'
import { propertyQueryParam } from '@/features/property-access-comparison/constants'
import type { PropertySummary } from '@/features/property-access-comparison'
import type { submitComparison } from '../../services'
import type { ComparisonRequest, ComparisonResponse, ComparisonSubmission } from '../../types'
import { readComparisonSubmission } from '../../utils'
import { ComparisonCriteriaForm } from '../ComparisonCriteriaForm'
import { ComparisonResults } from '../ComparisonResults'
import styles from './ComparisonAnalysis.module.css'

type ValidSubmission = Extract<ComparisonSubmission, { status: 'valid' }>
type Attempt = { submission: ValidSubmission, comparisonId?: string }
type Pending = 'analysis' | 'recalculation'
type Failure = { status: 'error' | 'unavailable', attempt: Attempt }

function analysisParams({ submission, comparisonId }: Attempt) {
  const params = new URLSearchParams({ criterios: '1', largura: submission.values.width })
  for (const id of submission.request.propertyIds) params.append(propertyQueryParam, id)
  if (submission.values.stepFree) params.set('degraus', '1')
  if (submission.values.ramp) params.set('rampa', '1')
  if (comparisonId !== undefined) params.set('comparacao', comparisonId)
  return params
}

function AnalysisWaiting() {
  const [stillRunning, setStillRunning] = useState(false)

  useEffect(() => {
    const timeout = window.setTimeout(() => setStillRunning(true), 30_000)
    return () => window.clearTimeout(timeout)
  }, [])

  return (
    <section className={styles.panel} aria-labelledby='analysis-waiting-title'>
      <div className={styles.progress} aria-hidden='true' />
      <h2 id='analysis-waiting-title'>Preparando sua comparação</h2>
      <p>Estamos consultando as informações de acesso dos imóveis selecionados. Isso costuma levar cerca de 30 segundos.</p>
      <p role='status'>{stillRunning ? 'A análise ainda está em andamento. O resultado aparecerá aqui.' : ''}</p>
    </section>
  )
}

export function ComparisonAnalysis({ propertyIds, initialSubmission, initialComparisonId, catalogProperties }: {
  propertyIds: ComparisonRequest['propertyIds']
  initialSubmission: ComparisonSubmission
  initialComparisonId?: string
  catalogProperties: PropertySummary[]
}) {
  const [submission, setSubmission] = useState(initialSubmission)
  const [comparisonId, setComparisonId] = useState(initialComparisonId)
  const [pending, setPending] = useState<Pending | null>(
    initialSubmission.status !== 'valid' ? null : initialComparisonId === undefined ? 'analysis' : 'recalculation',
  )
  const [result, setResult] = useState<{ submission: ValidSubmission, comparison: ComparisonResponse }>()
  const [failure, setFailure] = useState<Failure>()
  const [announcement, setAnnouncement] = useState('')
  const active = useRef<AbortController | null>(null)
  const form = useRef<HTMLFormElement | null>(null)

  const run = useCallback(async (attempt: Attempt) => {
    if (active.current) return
    const controller = new AbortController()
    active.current = controller
    const isNew = attempt.comparisonId === undefined
    setSubmission(attempt.submission)
    setPending(isNew ? 'analysis' : 'recalculation')
    setFailure(undefined)
    if (isNew) {
      setResult(undefined)
      setComparisonId(undefined)
    }
    setAnnouncement(isNew ? 'Análise iniciada.' : 'Atualizando comparação…')

    let outcome: Awaited<ReturnType<typeof submitComparison>>
    try {
      const response = await fetch('/comparar/analise', {
        method: 'POST',
        body: analysisParams(attempt),
        signal: controller.signal,
      })
      outcome = response.ok ? await response.json() : { status: 'error' }
    } catch {
      outcome = { status: 'error' }
    }

    if (controller.signal.aborted || active.current !== controller) return
    active.current = null
    const current = new URL(window.location.href)
    const currentIds = current.searchParams.getAll(propertyQueryParam)
    if (current.pathname !== '/comparar' ||
        currentIds.length !== propertyIds.length ||
        currentIds.some((id, index) => id !== propertyIds[index])) return

    setPending(null)
    if (outcome.status !== 'success') {
      setAnnouncement('')
      setFailure({ status: outcome.status, attempt })
      return
    }

    setResult({ submission: attempt.submission, comparison: outcome.comparison })
    setComparisonId(outcome.comparison.comparisonId)
    setAnnouncement(isNew ? 'Comparação concluída.' : 'Comparação atualizada.')
    const params = analysisParams({ ...attempt, comparisonId: outcome.comparison.comparisonId })
    window.history.replaceState(null, '', `/comparar?${params}`)
  }, [propertyIds])

  useEffect(() => {
    const start = window.setTimeout(() => {
      if (initialSubmission.status === 'valid') {
        void run({ submission: initialSubmission, comparisonId: initialComparisonId })
      }
    }, 0)
    return () => {
      window.clearTimeout(start)
      active.current?.abort()
      active.current = null
    }
  }, [initialComparisonId, initialSubmission, run])

  function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    if (pending || active.current) return
    const params = new FormData(event.currentTarget, event.nativeEvent.submitter)
    const values = Object.fromEntries(Array.from(params, ([key, value]) => [key, String(value)]))
    const next = readComparisonSubmission(propertyIds, values)
    if (next.status !== 'valid') {
      setSubmission(next)
      return
    }

    void run({ submission: next, comparisonId: values.novaAnalise === '1' ? undefined : comparisonId })
  }

  function retry() {
    if (!failure || pending || active.current) return
    form.current?.reset()
    void run({
      submission: failure.attempt.submission,
      comparisonId: failure.status === 'unavailable' ? undefined : failure.attempt.comparisonId,
    })
  }

  return (
    <>
      <ComparisonCriteriaForm
        formRef={form}
        propertyIds={propertyIds}
        submission={submission}
        comparisonId={comparisonId}
        pending={pending}
        onSubmit={submit}
        announcement={announcement}
      />

      {pending === 'analysis' && <AnalysisWaiting />}
      {pending === 'recalculation' && <p className={styles.updating}>Atualizando comparação…</p>}

      {failure && (
        <div className={styles.panel}>
          <p role='alert'>{failure.status === 'unavailable'
            ? 'A análise anterior expirou ou não está disponível para estes imóveis.'
            : 'Não foi possível concluir a comparação.'}</p>
          <button type='button' className={`${ui.button} ${ui.secondary}`} onClick={retry}>
            {failure.status === 'unavailable' ? 'Executar nova análise' : 'Tentar novamente'}
          </button>
        </div>
      )}

      {result && <ComparisonResults {...result} catalogProperties={catalogProperties} />}
    </>
  )
}

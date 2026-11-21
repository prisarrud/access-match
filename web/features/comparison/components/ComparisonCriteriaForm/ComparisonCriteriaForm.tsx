import { propertyQueryParam } from '@/features/property-access-comparison'
import type { ComparisonRequest, ComparisonSubmission } from '../../types'
import styles from './ComparisonCriteriaForm.module.css'

type ComparisonCriteriaFormProps = {
  propertyIds: ComparisonRequest['propertyIds']
  submission: ComparisonSubmission
  comparisonId?: string
}

export function ComparisonCriteriaForm({ propertyIds, submission, comparisonId }: ComparisonCriteriaFormProps) {
  const { values } = submission
  const errors = submission.status === 'invalid' ? submission.errors : undefined

  return (
    <form id='criterios' action='/comparar#criterios' method='get' className={styles.form}
      aria-labelledby='comparison-criteria-title'>
      {propertyIds.map((id) => (
        <input key={id} type='hidden' name={propertyQueryParam} value={id} />
      ))}

      <input type='hidden' name='criterios' value='1' />

      {comparisonId !== undefined && <input type='hidden' name='comparacao' value={comparisonId} />}

      <fieldset className={styles.fields}
        aria-describedby={errors?.criteria ? 'comparison-criteria-help comparison-criteria-error' : 'comparison-criteria-help'}>
        <legend id='comparison-criteria-title' className={styles.legend}>Critérios da comparação</legend>

        <p id='comparison-criteria-help' className={styles.help}>
          Todos os campos são opcionais. Informe pelo menos um critério.
        </p>

        {errors?.criteria && (
          <p id='comparison-criteria-error' className={styles.error} role='alert'>{errors.criteria}</p>
        )}

        <label className={styles.option}>
          <input type='checkbox' name='degraus' value='1' defaultChecked={values.stepFree} />
          Verificar acesso sem degraus
        </label>

        <label className={styles.option}>
          <input type='checkbox' name='rampa' value='1' defaultChecked={values.ramp} />
          Verificar presença de rampa
        </label>

        <div className={styles.width}>
          <label htmlFor='comparison-width'>Largura livre mínima da passagem (cm)</label>

          <input id='comparison-width' name='largura' type='text' inputMode='decimal'
            defaultValue={values.width}
            aria-invalid={errors?.width ? true : undefined}
            aria-describedby={errors?.width ? 'comparison-width-error' : undefined} />
          {errors?.width && (
            <p id='comparison-width-error' className={styles.error} role='alert'>{errors.width}</p>
          )}
        </div>
      </fieldset>

      <button type='submit' className='button button-primary'>
        {comparisonId === undefined ? 'Confirmar critérios' : 'Atualizar comparação'}
      </button>

      {submission.status === 'valid' && <p role='status'>Critérios registrados para esta seleção.</p>}
    </form>
  )
}

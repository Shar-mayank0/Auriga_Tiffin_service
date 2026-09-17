import { useForm } from 'react-hook-form'
import { today } from '../utils/dateHelpers.js'

export default function PauseForm({ onSubmit, disabled }) {
  const { register, handleSubmit, watch, formState: { errors } } = useForm({ defaultValues: { start_date: today(), end_date: '' } })
  const startDate = watch('start_date')
  return (
    <form className="form" onSubmit={handleSubmit(onSubmit)}>
      <label>Pause from<input type="date" {...register('start_date', { required: 'Choose a start date.' })} /></label>
      {errors.start_date && <p className="error">{errors.start_date.message}</p>}
      <label>Pause until (optional)<input type="date" min={startDate} {...register('end_date')} /></label>
      <button className="button" type="submit" disabled={disabled}>Pause service</button>
    </form>
  )
}
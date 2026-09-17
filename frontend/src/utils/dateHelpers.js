import { format, isValid, parseISO } from 'date-fns'

const toDate = (value) => (value instanceof Date ? value : parseISO(value))

export function formatDate(value) {
  const date = toDate(value)
  return isValid(date) ? format(date, 'dd MMM yyyy') : 'Not set'
}

export function formatMonth(value) {
  const date = toDate(value)
  return isValid(date) ? format(date, 'MMMM yyyy') : 'Unknown month'
}

export const today = () => format(new Date(), 'yyyy-MM-dd')
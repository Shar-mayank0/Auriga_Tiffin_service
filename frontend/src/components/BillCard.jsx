import { formatMonth } from '../utils/dateHelpers.js'

export default function BillCard({ bill }) {
  return (
    <article className="bill-card">
      <div>
        <p className="eyebrow">{formatMonth(bill.billing_month)}</p>
        <h2>{bill.plan_name || 'Tiffin plan'}</h2>
        <p>{bill.delivered_weekdays} of {bill.total_weekdays_in_segment} weekdays delivered</p>
      </div>
      <strong>₹{bill.amount_due}</strong>
    </article>
  )
}
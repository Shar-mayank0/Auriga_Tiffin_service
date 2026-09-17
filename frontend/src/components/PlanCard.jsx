export default function PlanCard({ plan, selected, onSelect }) {
  return (
    <article className={`plan-card ${selected ? 'selected' : ''}`}>
      <div>
        <h2>{plan.name}</h2>
        <p className="price">₹{plan.monthly_price}<span>/month</span></p>
      </div>
      <button type="button" className="button" onClick={() => onSelect(plan.id)}>
        {selected ? 'Selected' : 'Choose plan'}
      </button>
    </article>
  )
}
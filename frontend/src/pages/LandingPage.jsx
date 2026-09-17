import { Link } from 'react-router-dom'

export default function LandingPage() {
  return (
    <section className="landing">
      <p className="eyebrow">Fresh food, delivered simply</p>
      <h1>Your everyday tiffin, taken care of.</h1>
      <p className="lead">Choose a plan, pause when life changes, and keep your meals moving on your schedule.</p>
      <div className="actions"><Link className="button" to="/register">Create an account</Link><Link className="text-link" to="/login">Already a member? Log in</Link></div>
    </section>
  )
}
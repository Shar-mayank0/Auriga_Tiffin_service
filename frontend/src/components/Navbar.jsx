import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'

export default function Navbar() {
  const { isAuthenticated, logout } = useAuth()
  const navigate = useNavigate()
  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }
  return (
    <header className="navbar">
      <Link className="brand" to="/">Auriga Tiffin</Link>
      <nav>
        {isAuthenticated ? (
          <>
            <Link to="/dashboard">Dashboard</Link>
            <Link to="/billing">Billing</Link>
            <button type="button" className="link-button" onClick={handleLogout}>Log out</button>
          </>
        ) : (
          <>
            <Link to="/login">Log in</Link>
            <Link className="button button-small" to="/register">Register</Link>
          </>
        )}
      </nav>
    </header>
  )
}
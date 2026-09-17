import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import Navbar from './components/Navbar.jsx'
import ProtectedRoute from './components/ProtectedRoute.jsx'
import BillingPage from './pages/BillingPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import LandingPage from './pages/LandingPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import PausePage from './pages/PausePage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import SubscribePage from './pages/SubscribePage.jsx'

function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <main className="page-shell">
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/subscribe" element={<SubscribePage />} />
            <Route path="/pause" element={<PausePage />} />
            <Route path="/billing" element={<BillingPage />} />
          </Route>
          <Route path="*" element={<div className="empty-state"><h1>Page not found</h1><Link to="/">Return home</Link></div>} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}

export default App

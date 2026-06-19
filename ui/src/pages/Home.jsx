import { Link } from 'react-router-dom'
import Nav from '../components/Nav'
import { useAuth } from '../auth/AuthContext'
import './Home.css'

const AGENTS = [
  {
    name: 'Scout',
    role: 'Contract Researcher',
    color: '#ffa657',
    icon: '🏛',
    desc: 'Searches SAM.gov, Florida VBS, Bonfire, OpenGov, and municipal portals for contract opportunities. Manages your bid pipeline, tracks deadlines, and generates reports.',
  },
  {
    name: 'Greta',
    role: 'Bid Scorer (coming soon)',
    color: '#8b949e',
    icon: '⭐',
    desc: 'Scores and ranks opportunities by relevance to your company profile, NAICS codes, and set-aside eligibility. Routes the best leads to the top of your pipeline.',
  },
]

export default function Home() {
  const { isAuthenticated } = useAuth()

  return (
    <div className="home-page">
      <Nav />

      <section className="hero">
        <div className="hero-inner">
          <div className="hero-badge">Multi-Agent AI Platform</div>
          <h1 className="hero-title">Meet <span className="accent">William</span></h1>
          <p className="hero-sub">
            A supervisor AI that coordinates a team of specialist agents — from coding
            and research to document creation and government contracting.
          </p>
          <div className="hero-actions">
            {isAuthenticated
              ? <Link to="/chat" className="btn-primary">Open William →</Link>
              : <Link to="/login" className="btn-primary">Sign In to Get Started →</Link>
            }
            <Link to="/contact" className="btn-ghost">Contact Us</Link>
          </div>
        </div>
      </section>

      <section className="agents-section">
        <h2 className="section-title">The Team</h2>
        <p className="section-sub">William routes your request to the right specialist automatically.</p>
        <div className="agent-grid">
          {AGENTS.map(a => (
            <div key={a.name} className="agent-card">
              <div className="agent-icon" style={{ color: a.color }}>{a.icon}</div>
              <div className="agent-info">
                <div className="agent-name" style={{ color: a.color }}>{a.name}</div>
                <div className="agent-role">{a.role}</div>
                <div className="agent-desc">{a.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <footer className="home-footer">
        <span>William · Powered by AWS Bedrock</span>
        <Link to="/contact">Contact</Link>
      </footer>
    </div>
  )
}

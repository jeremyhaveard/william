import { useState } from 'react'
import Nav from '../components/Nav'
import './Contact.css'

export default function Contact() {
  const [form, setForm] = useState({ name: '', email: '', message: '' })
  const [status, setStatus] = useState(null) // 'sent' | 'error' | null

  function handleChange(e) {
    setForm(f => ({ ...f, [e.target.name]: e.target.value }))
  }

  function handleSubmit(e) {
    e.preventDefault()
    // Opens the user's mail client with the form fields pre-filled.
    // Replace the email address below with your own.
    const to      = 'hello@example.com'
    const subject = encodeURIComponent(`William enquiry from ${form.name}`)
    const body    = encodeURIComponent(
      `Name: ${form.name}\nEmail: ${form.email}\n\n${form.message}`
    )
    window.location.href = `mailto:${to}?subject=${subject}&body=${body}`
    setStatus('sent')
  }

  return (
    <div className="contact-page">
      <Nav />

      <div className="contact-wrap">
        <div className="contact-left">
          <h1 className="contact-title">Get in Touch</h1>
          <p className="contact-sub">
            Have a question about William, need access, or want to discuss
            a custom deployment? Send us a message.
          </p>

          <div className="contact-info">
            <div className="info-item">
              <span className="info-icon">✉</span>
              <span>hello@example.com</span>
            </div>
            <div className="info-item">
              <span className="info-icon">⏱</span>
              <span>We respond within one business day</span>
            </div>
          </div>
        </div>

        <form className="contact-form" onSubmit={handleSubmit}>
          {status === 'sent' && (
            <div className="form-success">
              Your mail client should have opened. If not, email us directly.
            </div>
          )}

          <div className="form-row">
            <label className="form-label" htmlFor="name">Name</label>
            <input
              id="name"
              name="name"
              className="form-input"
              type="text"
              placeholder="Your name"
              value={form.name}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-row">
            <label className="form-label" htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              className="form-input"
              type="email"
              placeholder="you@example.com"
              value={form.email}
              onChange={handleChange}
              required
            />
          </div>

          <div className="form-row">
            <label className="form-label" htmlFor="message">Message</label>
            <textarea
              id="message"
              name="message"
              className="form-input form-textarea"
              placeholder="How can we help?"
              rows={6}
              value={form.message}
              onChange={handleChange}
              required
            />
          </div>

          <button type="submit" className="form-submit">Send Message</button>
        </form>
      </div>

      <footer className="contact-footer">
        <span>William · Powered by AWS Bedrock</span>
      </footer>
    </div>
  )
}

import { useState } from 'react'

// ── Password strength ─────────────────────────────────────────────────────────
function getStrength(pw) {
  const checks = [
    { label: 'At least 12 characters',  ok: pw.length >= 12 },
    { label: 'Uppercase letter',         ok: /[A-Z]/.test(pw) },
    { label: 'Lowercase letter',         ok: /[a-z]/.test(pw) },
    { label: 'Number',                   ok: /[0-9]/.test(pw) },
    { label: 'Special character',        ok: /[^A-Za-z0-9]/.test(pw) },
  ]
  const score = checks.filter(c => c.ok).length
  return { checks, score, strong: score === 5 }
}

async function isBreached(password) {
  try {
    const buf  = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(password))
    const hex  = Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('').toUpperCase()
    const res  = await fetch(`https://api.pwnedpasswords.com/range/${hex.slice(0, 5)}`)
    const text = await res.text()
    return text.split('\n').some(line => line.startsWith(hex.slice(5)))
  } catch {
    return false  // Network error — don't block signup
  }
}

const STRENGTH_COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#16a34a']
const STRENGTH_LABELS = ['Very weak', 'Weak', 'Fair', 'Good', 'Strong']

function StrengthMeter({ password }) {
  if (!password) return null
  const { checks, score } = getStrength(password)
  const color = STRENGTH_COLORS[score - 1] || '#e5e7eb'
  const label = STRENGTH_LABELS[score - 1] || ''
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', gap: 4, marginBottom: 6 }}>
        {[1,2,3,4,5].map(i => (
          <div key={i} style={{
            flex: 1, height: 3, borderRadius: 2,
            background: i <= score ? color : '#e5e7eb',
            transition: 'background 0.2s',
          }} />
        ))}
      </div>
      <div style={{ fontSize: 11, color, fontWeight: 500, marginBottom: 4 }}>{label}</div>
      {checks.filter(c => !c.ok).map(c => (
        <div key={c.label} style={{ fontSize: 11, color: '#9ca3af', display: 'flex', gap: 4, alignItems: 'center' }}>
          <span>✕</span> {c.label}
        </div>
      ))}
    </div>
  )
}


export default function AuthPage({ onSignInGoogle, onSignInEmail, onSignUp, onSignInPhone, onVerifyOtp }) {
  const [mode, setMode]         = useState('signin')
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [phone, setPhone]       = useState('')
  const [otp, setOtp]           = useState('')
  const [otpSent, setOtpSent]   = useState(false)
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)

  const isSuccess = error.includes('Check') || error.includes('sent')

  const handleEmailAuth = async () => {
    setLoading(true)
    setError('')
    try {
      if (mode === 'signup') {
        const { score, strong } = getStrength(password)
        if (!strong) {
          setError('Password too weak — please meet all 5 requirements.')
          return
        }
        const breached = await isBreached(password)
        if (breached) {
          setError('This password has appeared in a data breach. Please choose a different one.')
          return
        }
        await onSignUp(email, password)
        setError('Check your email for a confirmation link.')
      } else {
        await onSignInEmail(email, password)
      }
    } catch (e) {
      setError(e.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const handlePhoneAuth = async () => {
    setLoading(true)
    setError('')
    try {
      if (!otpSent) {
        await onSignInPhone(phone)
        setOtpSent(true)
        setError('OTP sent to your phone.')
      } else {
        await onVerifyOtp(phone, otp)
      }
    } catch (e) {
      setError(e.message || 'Phone auth failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      background: '#fafaf8',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
    }}>
      <div style={{ width: 360, padding: '48px 0' }}>

        {/* Logo */}
        <div style={{
          fontFamily: "'Noto Serif', serif",
          fontSize: 28,
          fontWeight: 300,
          color: '#1a1a1a',
          marginBottom: 8,
          letterSpacing: '-0.02em',
        }}>AskMyDocs</div>
        <div style={{
          fontFamily: "'Noto Sans JP', sans-serif",
          fontSize: 11,
          fontWeight: 300,
          color: '#aaa',
          letterSpacing: '0.25em',
          textTransform: 'uppercase',
          marginBottom: 48,
        }}>Document Intelligence</div>

        {/* Mode tabs */}
        <div style={{ display: 'flex', borderBottom: '1px solid #d8d8d2', marginBottom: 32, gap: 0 }}>
          {['signin', 'signup', 'phone'].map(m => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(''); setPassword('') }}
              style={{
                background: 'transparent',
                border: 'none',
                borderBottom: mode === m ? '1px solid #1a1a1a' : 'none',
                marginBottom: mode === m ? -1 : 0,
                padding: '8px 16px 8px 0',
                fontSize: 11,
                fontFamily: "'Noto Sans JP', sans-serif",
                fontWeight: mode === m ? 400 : 300,
                letterSpacing: '0.15em',
                textTransform: 'uppercase',
                color: mode === m ? '#1a1a1a' : '#aaa',
                cursor: 'pointer',
              }}
            >
              {m === 'signin' ? 'Sign in' : m === 'signup' ? 'Sign up' : 'Phone'}
            </button>
          ))}
        </div>

        {/* Google */}
        <button
          onClick={onSignInGoogle}
          style={{
            width: '100%',
            background: '#fafaf8',
            border: '1px solid #d8d8d2',
            padding: '10px 20px',
            fontSize: 12,
            fontFamily: "'Noto Sans JP', sans-serif",
            fontWeight: 300,
            letterSpacing: '0.1em',
            color: '#1a1a1a',
            cursor: 'pointer',
            marginBottom: 24,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 10,
          }}
        >
          <svg width="16" height="16" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          Continue with Google
        </button>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24, color: '#d8d8d2', fontSize: 11 }}>
          <div style={{ flex: 1, height: 1, background: '#d8d8d2' }} />or
          <div style={{ flex: 1, height: 1, background: '#d8d8d2' }} />
        </div>

        {/* Email / Phone forms */}
        {mode !== 'phone' ? (
          <>
            <input
              className="input-field"
              type="email"
              placeholder="Email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleEmailAuth()}
            />
            <input
              className="input-field"
              type="password"
              placeholder={mode === 'signup' ? 'Password (min 12 characters)' : 'Password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleEmailAuth()}
            />
            {mode === 'signup' && <StrengthMeter password={password} />}
            <button
              className="btn-primary"
              onClick={handleEmailAuth}
              disabled={!email || !password || loading || (mode === 'signup' && !getStrength(password).strong)}
            >
              {loading ? '…' : mode === 'signup' ? 'Create account' : 'Sign in'}
            </button>
          </>
        ) : (
          <>
            <input
              className="input-field"
              type="tel"
              placeholder="+61 4XX XXX XXX"
              value={phone}
              onChange={e => setPhone(e.target.value)}
              disabled={otpSent}
            />
            {otpSent && (
              <input
                className="input-field"
                type="text"
                placeholder="Enter OTP"
                value={otp}
                onChange={e => setOtp(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handlePhoneAuth()}
              />
            )}
            <button
              className="btn-primary"
              onClick={handlePhoneAuth}
              disabled={!phone || loading}
            >
              {loading ? '…' : otpSent ? 'Verify OTP' : 'Send OTP'}
            </button>
          </>
        )}

        {error && (
          <div style={{
            marginTop: 16,
            fontSize: 12,
            fontFamily: "'Noto Sans JP', sans-serif",
            fontWeight: 300,
            color: isSuccess ? '#3a7a3a' : '#7a3a3a',
            borderLeft: `2px solid ${isSuccess ? '#3a7a3a' : '#7a3a3a'}`,
            padding: '8px 12px',
          }}>
            {error}
          </div>
        )}

        <div style={{ marginTop: 48, fontFamily: "'Noto Serif', sans-serif", fontSize: 10, color: '#ccc', letterSpacing: '0.2em', fontStyle: 'italic' }}>
          AskMyDocs · 2026
        </div>
      </div>
    </div>
  )
}

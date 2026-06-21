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


function EyeIcon({ open }) {
  return open ? (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
      <circle cx="12" cy="12" r="3"/>
    </svg>
  ) : (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
      <line x1="1" y1="1" x2="23" y2="23"/>
    </svg>
  )
}

export default function AuthPage({ onSignInEmail, onSignUp, onSignInPhone, onVerifyOtp }) {
  const [mode, setMode]                   = useState('signin')
  const [email, setEmail]                 = useState('')
  const [password, setPassword]           = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [confirmTouched, setConfirmTouched]   = useState(false)
  const [showPassword, setShowPassword]       = useState(false)
  const [showConfirm, setShowConfirm]         = useState(false)
  const [phone, setPhone]                 = useState('')
  const [otp, setOtp]                     = useState('')
  const [otpSent, setOtpSent]             = useState(false)
  const [error, setError]                 = useState('')
  const [loading, setLoading]             = useState(false)
  const [signupDone, setSignupDone]       = useState(false)
  const [resendCooldown, setResendCooldown] = useState(0)

  const passwordMismatch = confirmTouched && confirmPassword && password !== confirmPassword

  const startCooldown = () => {
    setResendCooldown(60)
    const t = setInterval(() => {
      setResendCooldown(prev => { if (prev <= 1) { clearInterval(t); return 0 } return prev - 1 })
    }, 1000)
  }

  const handleEmailAuth = async () => {
    setLoading(true)
    setError('')
    try {
      if (mode === 'signup') {
        const { strong } = getStrength(password)
        if (!strong) {
          setError('Password too weak — please meet all 5 requirements.')
          return
        }
        if (password !== confirmPassword) {
          setError('Passwords do not match.')
          return
        }
        const breached = await isBreached(password)
        if (breached) {
          setError('This password has appeared in a data breach. Please choose a different one.')
          return
        }
        await onSignUp(email, password)
        setSignupDone(true)
        startCooldown()
      } else {
        await onSignInEmail(email, password)
      }
    } catch (e) {
      setError(e.message || 'Authentication failed')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    if (resendCooldown > 0) return
    setLoading(true)
    try {
      await onSignUp(email, password)
      startCooldown()
    } catch (e) {
      setError(e.message || 'Failed to resend.')
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

  const wrap = (children) => (
    <div style={{ minHeight: '100vh', background: '#fafaf8', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div style={{ width: 360, padding: '48px 0' }}>
        <div style={{ fontFamily: "'Noto Serif', serif", fontSize: 28, fontWeight: 300, color: '#1a1a1a', marginBottom: 8, letterSpacing: '-0.02em' }}>AskMyDocs</div>
        <div style={{ fontFamily: "'Noto Sans JP', sans-serif", fontSize: 11, fontWeight: 300, color: '#aaa', letterSpacing: '0.25em', textTransform: 'uppercase', marginBottom: 48 }}>Document Intelligence</div>
        {children}
        <div style={{ marginTop: 48, fontFamily: "'Noto Serif', sans-serif", fontSize: 10, color: '#ccc', letterSpacing: '0.2em', fontStyle: 'italic' }}>AskMyDocs · 2026</div>
      </div>
    </div>
  )

  // ── Check-your-email screen ───────────────────────────────────────────────
  if (signupDone) {
    return wrap(
      <>
        <div style={{ fontSize: 18, fontWeight: 300, color: '#1a1a1a', marginBottom: 8 }}>Check your inbox</div>
        <div style={{ fontSize: 13, color: '#666', fontFamily: "'Noto Sans JP', sans-serif", fontWeight: 300, marginBottom: 4 }}>
          We sent a confirmation link to
        </div>
        <div style={{ fontSize: 13, color: '#1a1a1a', fontWeight: 400, marginBottom: 32 }}>{email}</div>
        <div style={{ fontSize: 12, color: '#aaa', fontFamily: "'Noto Sans JP', sans-serif", fontWeight: 300, marginBottom: 24 }}>
          Click the link in the email to verify your account. Check your spam folder if you don't see it.
        </div>
        <button
          className="btn-primary"
          onClick={handleResend}
          disabled={resendCooldown > 0 || loading}
        >
          {loading ? '…' : resendCooldown > 0 ? `Resend in ${resendCooldown}s` : 'Resend email'}
        </button>
        <button
          onClick={() => { setSignupDone(false); setMode('signin') }}
          style={{ background: 'none', border: 'none', marginTop: 16, fontSize: 11, color: '#aaa', cursor: 'pointer', fontFamily: "'Noto Sans JP', sans-serif", letterSpacing: '0.1em' }}
        >
          Back to sign in
        </button>
      </>
    )
  }

  const pwFieldStyle = { position: 'relative', marginBottom: 12 }
  const eyeStyle = {
    position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
    background: 'none', border: 'none', cursor: 'pointer', color: '#aaa', padding: 0, display: 'flex',
  }

  return wrap(
    <>
      {/* Mode tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid #d8d8d2', marginBottom: 32, gap: 0 }}>
        {['signin', 'signup', 'phone'].map(m => (
          <button
            key={m}
            onClick={() => { setMode(m); setError(''); setPassword(''); setConfirmPassword(''); setConfirmTouched(false) }}
            style={{
              background: 'transparent', border: 'none',
              borderBottom: mode === m ? '1px solid #1a1a1a' : 'none',
              marginBottom: mode === m ? -1 : 0,
              padding: '8px 16px 8px 0', fontSize: 11,
              fontFamily: "'Noto Sans JP', sans-serif",
              fontWeight: mode === m ? 400 : 300,
              letterSpacing: '0.15em', textTransform: 'uppercase',
              color: mode === m ? '#1a1a1a' : '#aaa', cursor: 'pointer',
            }}
          >
            {m === 'signin' ? 'Sign in' : m === 'signup' ? 'Sign up' : 'Phone'}
          </button>
        ))}
      </div>

      {mode !== 'phone' ? (
        <>
          <input
            className="input-field"
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleEmailAuth()}
            style={{ marginBottom: 12 }}
          />

          {/* Password with eye toggle */}
          <div style={pwFieldStyle}>
            <input
              className="input-field"
              type={showPassword ? 'text' : 'password'}
              placeholder={mode === 'signup' ? 'Password (min 12 characters)' : 'Password'}
              value={password}
              onChange={e => setPassword(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleEmailAuth()}
              style={{ marginBottom: 0, paddingRight: 40 }}
            />
            <button style={eyeStyle} onClick={() => setShowPassword(v => !v)} tabIndex={-1} type="button" aria-label={showPassword ? 'Hide password' : 'Show password'}>
              <EyeIcon open={showPassword} />
            </button>
          </div>

          {mode === 'signup' && (
            <>
              <StrengthMeter password={password} />

              {/* Confirm password */}
              <div style={pwFieldStyle}>
                <input
                  className="input-field"
                  type={showConfirm ? 'text' : 'password'}
                  placeholder="Confirm password"
                  value={confirmPassword}
                  onChange={e => setConfirmPassword(e.target.value)}
                  onBlur={() => setConfirmTouched(true)}
                  onKeyDown={e => e.key === 'Enter' && handleEmailAuth()}
                  style={{ marginBottom: 0, paddingRight: 40, borderColor: passwordMismatch ? '#ef4444' : undefined }}
                  aria-invalid={passwordMismatch}
                />
                <button style={eyeStyle} onClick={() => setShowConfirm(v => !v)} tabIndex={-1} type="button" aria-label={showConfirm ? 'Hide password' : 'Show password'}>
                  <EyeIcon open={showConfirm} />
                </button>
              </div>
              {passwordMismatch && (
                <div style={{ fontSize: 11, color: '#ef4444', marginBottom: 8 }}>Passwords do not match</div>
              )}
            </>
          )}

          <button
            className="btn-primary"
            onClick={handleEmailAuth}
            disabled={
              !email || !password || loading ||
              (mode === 'signup' && (!getStrength(password).strong || !confirmPassword || password !== confirmPassword))
            }
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
          marginTop: 16, fontSize: 12,
          fontFamily: "'Noto Sans JP', sans-serif", fontWeight: 300,
          color: '#7a3a3a', borderLeft: '2px solid #7a3a3a', padding: '8px 12px',
        }}>
          {error}
        </div>
      )}
    </>
  )
}

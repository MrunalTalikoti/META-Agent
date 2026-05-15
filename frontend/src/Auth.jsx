import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

const s = {
  page: {
    display: 'flex',
    minHeight: '100vh',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    background: '#000',
    color: '#fff',
  },
  left: {
    flex: 1,
    background: '#000',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    padding: '32px',
    position: 'relative',
    overflow: 'hidden',
  },
  right: {
    width: '480px',
    minWidth: '380px',
    background: '#0d0d0d',
    display: 'flex',
    flexDirection: 'column',
    padding: '32px 52px',
    position: 'relative',
  },
  brand: {
    color: '#fff',
    fontSize: '14px',
    fontWeight: 500,
    letterSpacing: '0.02em',
    position: 'relative',
    zIndex: 1,
  },
  copyright: {
    color: 'rgba(255,255,255,0.28)',
    fontSize: '11px',
    position: 'relative',
    zIndex: 1,
  },
  starWrap: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    position: 'relative',
    zIndex: 1,
  },
  topLink: {
    background: 'none',
    border: 'none',
    color: 'rgba(255,255,255,0.45)',
    fontSize: '13px',
    cursor: 'pointer',
    padding: 0,
    fontFamily: 'inherit',
    textAlign: 'right',
  },
  heading: {
    fontFamily: "'Chiqueta', 'Inter', sans-serif",
    color: '#fff',
    fontSize: '56px',
    fontWeight: 400,
    margin: '0 0 44px 0',
    letterSpacing: '0.01em',
    lineHeight: 1,
  },
  label: {
    display: 'block',
    color: 'rgba(255,255,255,0.45)',
    fontSize: '11px',
    letterSpacing: '0.04em',
    marginBottom: '10px',
  },
  input: {
    width: '100%',
    background: 'transparent',
    border: 'none',
    borderBottom: '1px solid rgba(255,255,255,0.15)',
    color: '#fff',
    fontSize: '15px',
    padding: '8px 0',
    outline: 'none',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
    transition: 'border-color 0.2s',
  },
  eyeBtn: {
    position: 'absolute',
    right: 0,
    top: '50%',
    transform: 'translateY(-50%)',
    background: 'none',
    border: 'none',
    color: 'rgba(255,255,255,0.35)',
    cursor: 'pointer',
    padding: 0,
    fontSize: '15px',
    lineHeight: 1,
    fontFamily: 'inherit',
  },
  rememberLabel: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    cursor: 'pointer',
    color: 'rgba(255,255,255,0.45)',
    fontSize: '13px',
  },
  forgotBtn: {
    background: 'none',
    border: 'none',
    color: 'rgba(255,255,255,0.45)',
    fontSize: '13px',
    cursor: 'pointer',
    padding: 0,
    fontFamily: 'inherit',
  },
  errorMsg: {
    color: '#ff6b6b',
    fontSize: '13px',
  },
  submitBtn: {
    width: '76px',
    height: '76px',
    borderRadius: '50%',
    background: '#fff',
    color: '#000',
    border: 'none',
    fontSize: '10px',
    fontWeight: 700,
    letterSpacing: '0.1em',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    textAlign: 'center',
    fontFamily: 'inherit',
    lineHeight: 1.3,
    flexShrink: 0,
    transition: 'opacity 0.15s',
  },
};

export default function Auth() {
  const { user, login, register } = useAuth();
  const [mode, setMode]               = useState('login');
  const [email, setEmail]             = useState('');
  const [password, setPassword]       = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe]   = useState(false);
  const [error, setError]             = useState('');
  const [loading, setLoading]         = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (mode === 'login') await login(email, password);
      else                  await register(email, password);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggle = () => { setMode(m => m === 'login' ? 'register' : 'login'); setError(''); };

  return (
    <div style={s.page}>
      {/* ── Left Panel ── */}
      <div style={s.left}>
        {/* Subtle background lines */}
        <svg
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}
          preserveAspectRatio="none"
          xmlns="http://www.w3.org/2000/svg"
        >
          <line x1="0" y1="0" x2="100%" y2="100%" stroke="rgba(255,255,255,0.07)" strokeWidth="1" />
          <line x1="100%" y1="0" x2="0" y2="100%" stroke="rgba(255,255,255,0.07)" strokeWidth="1" />
          <line x1="50%" y1="0" x2="50%" y2="100%" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
          <line x1="0" y1="50%" x2="100%" y2="50%" stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
        </svg>

        <div style={s.brand}>Meta-Agent°</div>

        {/* Asterisk / star symbol */}
        <div style={s.starWrap}>
          <svg width="150" height="150" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
            {/* 4 lines = 8 spokes */}
            <line x1="50" y1="4"  x2="50" y2="96" stroke="white" strokeWidth="1.4" />
            <line x1="4"  y1="50" x2="96" y2="50" stroke="white" strokeWidth="1.4" />
            <line x1="14" y1="14" x2="86" y2="86" stroke="white" strokeWidth="1.4" />
            <line x1="86" y1="14" x2="14" y2="86" stroke="white" strokeWidth="1.4" />
          </svg>
        </div>

        <div style={s.copyright}>© Meta-Agent 2024. All rights reserved.</div>
      </div>

      {/* ── Right Panel ── */}
      <div style={s.right}>
        <form
          onSubmit={submit}
          style={{ display: 'flex', flexDirection: 'column', height: '100%' }}
          noValidate
        >
          {/* Top toggle */}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="button" style={s.topLink} onClick={toggle}>
              {mode === 'login' ? 'Create an account' : 'Sign in instead'}
            </button>
          </div>

          {/* Fields */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', gap: '28px' }}>
            <h1 style={s.heading}>
              {mode === 'login' ? 'Login' : 'Register'}
            </h1>

            {/* Email */}
            <div>
              <label style={s.label}>Email</label>
              <input
                type="email"
                autoComplete="email"
                placeholder="your@email.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                style={s.input}
                onFocus={e  => (e.target.style.borderBottomColor = 'rgba(255,255,255,0.6)')}
                onBlur={e   => (e.target.style.borderBottomColor = 'rgba(255,255,255,0.15)')}
              />
            </div>

            {/* Password */}
            <div>
              <label style={s.label}>Password</label>
              <div style={{ position: 'relative' }}>
                <input
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  required
                  minLength={mode === 'register' ? 8 : undefined}
                  style={{ ...s.input, paddingRight: '28px' }}
                  onFocus={e => (e.target.style.borderBottomColor = 'rgba(255,255,255,0.6)')}
                  onBlur={e  => (e.target.style.borderBottomColor = 'rgba(255,255,255,0.15)')}
                />
                <button
                  type="button"
                  style={s.eyeBtn}
                  onClick={() => setShowPassword(v => !v)}
                  tabIndex={-1}
                >
                  {showPassword ? '○' : '◉'}
                </button>
              </div>
            </div>

            {/* Remember me + Forgot */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <label style={s.rememberLabel}>
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={e => setRememberMe(e.target.checked)}
                  style={{ accentColor: '#fff', width: '13px', height: '13px' }}
                />
                Remember me
              </label>
              {mode === 'login' && (
                <button type="button" style={s.forgotBtn}>Forgot?</button>
              )}
            </div>

            {error && <div style={s.errorMsg}>{error}</div>}
          </div>

          {/* Submit */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '32px' }}>
            <button
              type="submit"
              disabled={loading}
              style={{ ...s.submitBtn, opacity: loading ? 0.5 : 1 }}
            >
              {loading ? '...' : mode === 'login' ? 'SIGN\nIN' : 'JOIN'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

import { useState } from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from './AuthContext';

export default function Auth() {
  const { user, login, register } = useAuth();
  const [mode, setMode]           = useState('login');
  const [email, setEmail]         = useState('');
  const [password, setPassword]   = useState('');
  const [error, setError]         = useState('');
  const [loading, setLoading]     = useState(false);

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
    <div className="min-h-screen bg-black font-term crt flex flex-col items-center justify-center px-4">
      {/* Logo */}
      <div className="text-center mb-10">
        <div
          className="logo-pixel mb-3"
          style={{ fontSize: 'clamp(0.85rem, 2.5vw, 1.6rem)' }}
        >
          META-AGENT
        </div>
        <div className="text-g-dim text-lg">ai orchestration platform v0.2.0</div>
      </div>

      {/* Auth panel */}
      <div className="w-full max-w-md border border-g-bright glow-box p-7">
        <div className="text-g-dim text-base mb-6">
          {'>'} {mode === 'login' ? 'AUTHENTICATE' : 'CREATE ACCOUNT'}
        </div>

        <form onSubmit={submit} className="space-y-5">
          <div className="flex items-center gap-3">
            <span className="text-g-dim w-28 shrink-0">email:</span>
            <input
              type="email"
              autoComplete="email"
              className="tinput flex-1"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
            />
          </div>

          <div className="flex items-center gap-3">
            <span className="text-g-dim w-28 shrink-0">password:</span>
            <input
              type="password"
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              className="tinput flex-1"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              minLength={mode === 'register' ? 8 : undefined}
            />
          </div>

          {error && (
            <div className="text-red-400 text-base">{'>'} ERROR: {error}</div>
          )}

          <div className="flex gap-3 pt-1">
            <button type="submit" className="tbtn" disabled={loading}>
              {loading ? 'PROCESSING...' : mode === 'login' ? 'LOGIN' : 'REGISTER'}
            </button>
            <button type="button" className="tbtn" onClick={toggle}>
              {mode === 'login' ? 'REGISTER' : 'LOGIN'}
            </button>
          </div>
        </form>
      </div>

      {/* Blinking cursor at bottom */}
      <div className="mt-6 text-g-dim text-base">
        <span className="cursor" />
      </div>
    </div>
  );
}

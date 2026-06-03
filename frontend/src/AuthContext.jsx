import { createContext, useContext, useState, useEffect } from 'react';
import {
  api,
  getToken,
  getRefreshToken,
  setTokens,
  clearTokens,
  setAuthFailureHandler,
} from './api';

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null);
  const [loading, setLoading] = useState(true);

  // When the api layer exhausts its refresh attempt, force a clean logout.
  useEffect(() => {
    setAuthFailureHandler(() => {
      clearTokens();
      setUser(null);
    });
    return () => setAuthFailureHandler(null);
  }, []);

  // Validate stored token on boot and load full user profile.
  // getMetrics() now auto-refreshes a stale access token under the hood, so a
  // returning user with a live refresh token stays logged in across reloads.
  useEffect(() => {
    if (!getToken()) { setLoading(false); return; }
    api.getMetrics()
      .then(m => setUser({
        id:             m.user_id,
        tier:           m.tier,
        email:          localStorage.getItem('ma_email') ?? '',
        requestsToday:  m.requests_today,
      }))
      .catch(() => clearTokens())
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const data = await api.login(email, password);
    setTokens(data);
    localStorage.setItem('ma_email', email);
    // Fetch full profile immediately
    const m = await api.getMetrics().catch(() => null);
    setUser({
      id:             m?.user_id ?? null,
      tier:           m?.tier ?? 'free',
      email,
      requestsToday:  m?.requests_today ?? 0,
    });
  };

  const register = async (email, password) => {
    await api.register(email, password);
    await login(email, password);
  };

  const logout = async () => {
    const refresh = getRefreshToken();
    // Best-effort server-side revocation; never block local logout on it.
    if (refresh) await api.logout(refresh).catch(() => {});
    clearTokens();
    setUser(null);
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-black text-g-bright font-term text-2xl">
        <span className="cursor">LOADING</span>
      </div>
    );
  }

  return (
    <AuthCtx.Provider value={{ user, login, register, logout }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);

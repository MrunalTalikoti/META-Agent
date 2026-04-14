import { createContext, useContext, useState, useEffect } from 'react';
import { api } from './api';

const AuthCtx = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser]     = useState(null);
  const [loading, setLoading] = useState(true);

  // Validate stored token on boot
  useEffect(() => {
    const token = localStorage.getItem('ma_token');
    if (!token) { setLoading(false); return; }
    api.getMetrics()
      .then(m => setUser({ id: m.user_id, tier: m.tier }))
      .catch(() => localStorage.removeItem('ma_token'))
      .finally(() => setLoading(false));
  }, []);

  const login = async (email, password) => {
    const data = await api.login(email, password);
    localStorage.setItem('ma_token', data.access_token);
    setUser({ email });
  };

  const register = async (email, password) => {
    await api.register(email, password);
    await login(email, password);
  };

  const logout = () => {
    localStorage.removeItem('ma_token');
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

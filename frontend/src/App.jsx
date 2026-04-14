import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Auth from './Auth';
import Dashboard from './Dashboard';
import Conversation from './Conversation';
import Metrics from './Metrics';

function Guard({ children }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/auth" replace />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/auth" element={<Auth />} />
          <Route path="/" element={<Guard><Dashboard /></Guard>} />
          <Route path="/c/:id" element={<Guard><Conversation /></Guard>} />
          <Route path="/metrics" element={<Guard><Metrics /></Guard>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

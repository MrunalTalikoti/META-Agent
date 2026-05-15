import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { api } from './api';

const MODE_INFO = {
  normal: {
    label: 'Normal',
    hint:  'Execute immediately — agents run in parallel once requirements are clear.',
    agents: ['code_generator', 'api_designer', 'database_schema', 'testing_agent',
             'frontend_generator', 'devops', 'security_auditor', 'documentation_agent', 'performance_optimizer'],
  },
  hardcore: {
    label: 'Hardcore',
    hint:  'Requirements first — agent asks clarifying questions before executing.',
    agents: ['requirements_gatherer', '→ all agents'],
  },
};

export default function Layout({ children, status }) {
  const [showModal, setShowModal]     = useState(false);
  const [projects, setProjects]       = useState([]);
  const [selProject, setSelProject]   = useState(null);
  const [newProjName, setNewProjName] = useState('');
  const [newProjDesc, setNewProjDesc] = useState('');
  const [mode, setMode]               = useState('normal');
  const [message, setMessage]         = useState('');
  const [creating, setCreating]       = useState(false);
  const [error, setError]             = useState('');
  const [sidebarKey, setSidebarKey]   = useState(0);
  const navigate                      = useNavigate();

  const openModal = async () => {
    setError(''); setMessage(''); setNewProjName(''); setNewProjDesc(''); setMode('normal');
    const ps = await api.getProjects().catch(() => []);
    setProjects(ps);
    setSelProject(ps[0] ?? null);
    setShowModal(true);
  };

  const createSession = async (e) => {
    e.preventDefault();
    if (!message.trim()) { setError('Message is required'); return; }
    setCreating(true); setError('');
    try {
      let proj = selProject;
      if (!proj) {
        const name = newProjName.trim() || `project_${Date.now()}`;
        proj = await api.createProject(name, newProjDesc.trim());
        setSidebarKey(k => k + 1);
      }
      const conv = await api.createConversation(proj.id, mode, message.trim());
      setShowModal(false);
      navigate(`/c/${conv.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const modeInfo = MODE_INFO[mode];

  return (
    <div style={{
      display: 'flex',
      height: '100vh',
      background: '#000',
      overflow: 'hidden',
      fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    }}>
      <Sidebar onNewSession={openModal} refreshKey={sidebarKey} />

      {/* Main area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
        {children}

        {/* Status bar */}
        <div style={{
          flexShrink: 0,
          borderTop: '1px solid rgba(255,255,255,0.07)',
          padding: '6px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
        }}>
          <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.1em', color: 'rgba(255,255,255,0.25)', textTransform: 'uppercase' }}>
            {status || 'Ready — API Online'}
          </span>
          <span style={{ marginLeft: 'auto', fontSize: '10px', color: 'rgba(255,255,255,0.18)', letterSpacing: '0.05em' }}>
            {new Date().toLocaleTimeString('en-US', { hour12: false })}
          </span>
        </div>
      </div>

      {/* ── New Session Modal ── */}
      {showModal && (
        <div
          style={{
            position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
            backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center',
            justifyContent: 'center', zIndex: 50, padding: '16px',
          }}
          onClick={e => e.target === e.currentTarget && setShowModal(false)}
        >
          <div style={{
            background: '#0d0d0d',
            border: '1px solid rgba(255,255,255,0.1)',
            width: '100%', maxWidth: '520px',
            padding: '36px 40px',
            maxHeight: '90vh', overflowY: 'auto',
          }}>
            {/* Heading */}
            <div style={{ marginBottom: '32px' }}>
              <div style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '0.18em', color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', marginBottom: '8px' }}>
                New Session
              </div>
              <div style={{ fontFamily: "'Chiqueta', 'Inter', sans-serif", fontSize: '30px', fontWeight: 400, letterSpacing: '0.01em', color: '#fff' }}>
                What do you want to build?
              </div>
            </div>

            <form onSubmit={createSession}>

              {/* Project */}
              <div style={{ marginBottom: '24px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.35)', marginBottom: '10px' }}>
                  Project
                </div>
                {projects.length > 0 && (
                  <select
                    style={{
                      width: '100%', background: '#111', border: '1px solid rgba(255,255,255,0.12)',
                      color: '#fff', fontFamily: 'inherit', fontSize: '14px',
                      padding: '8px 12px', outline: 'none', borderRadius: '2px',
                    }}
                    value={selProject?.id ?? ''}
                    onChange={e => {
                      const p = projects.find(x => x.id === parseInt(e.target.value));
                      setSelProject(p ?? null);
                    }}
                  >
                    <option value="">— Create new project —</option>
                    {projects.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                )}
                {!selProject && (
                  <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <input
                      className="tinput"
                      placeholder="Project name..."
                      value={newProjName}
                      onChange={e => setNewProjName(e.target.value)}
                    />
                    <input
                      className="tinput"
                      placeholder="Description (optional)..."
                      value={newProjDesc}
                      onChange={e => setNewProjDesc(e.target.value)}
                    />
                  </div>
                )}
              </div>

              {/* Mode */}
              <div style={{ marginBottom: '24px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.35)', marginBottom: '10px' }}>
                  Mode
                </div>
                <div style={{ display: 'flex', gap: '8px', marginBottom: '10px' }}>
                  {Object.keys(MODE_INFO).map(m => (
                    <button
                      key={m}
                      type="button"
                      className={`tbtn ${mode === m ? 'active' : ''}`}
                      onClick={() => setMode(m)}
                    >
                      {MODE_INFO[m].label}
                    </button>
                  ))}
                </div>
                <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', lineHeight: '1.5', marginBottom: '8px' }}>
                  {modeInfo.hint}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {modeInfo.agents.map(a => (
                    <span key={a} style={{
                      border: '1px solid rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.3)',
                      fontSize: '10px', padding: '2px 8px', borderRadius: '2px', fontWeight: 500,
                      letterSpacing: '0.05em',
                    }}>
                      {a.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>

              {/* Message */}
              <div style={{ marginBottom: '24px' }}>
                <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.35)', marginBottom: '10px' }}>
                  Describe what to build
                </div>
                <textarea
                  autoFocus
                  style={{
                    width: '100%', background: '#111', border: '1px solid rgba(255,255,255,0.12)',
                    color: '#fff', fontFamily: 'inherit', fontSize: '14px', lineHeight: '1.6',
                    padding: '12px', outline: 'none', resize: 'none', borderRadius: '2px',
                    transition: 'border-color 0.2s',
                  }}
                  placeholder="Build a REST API for a todo app with authentication..."
                  rows={4}
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                  onFocus={e => (e.target.style.borderColor = 'rgba(255,255,255,0.3)')}
                  onBlur={e  => (e.target.style.borderColor = 'rgba(255,255,255,0.12)')}
                />
                <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.2)', textAlign: 'right', marginTop: '4px' }}>
                  {message.length}/5000
                </div>
              </div>

              {error && (
                <div style={{ color: '#ff6b6b', fontSize: '13px', marginBottom: '16px' }}>
                  {error}
                </div>
              )}

              <div style={{ display: 'flex', gap: '10px' }}>
                <button
                  type="submit"
                  disabled={creating}
                  style={{
                    flex: 1, padding: '10px', background: '#fff', color: '#000',
                    border: 'none', fontSize: '11px', fontWeight: 700, letterSpacing: '0.12em',
                    textTransform: 'uppercase', cursor: creating ? 'not-allowed' : 'pointer',
                    opacity: creating ? 0.5 : 1, borderRadius: '2px', fontFamily: 'inherit',
                    transition: 'opacity 0.15s',
                  }}
                >
                  {creating ? 'Launching...' : 'Start Session'}
                </button>
                <button
                  type="button"
                  className="tbtn"
                  onClick={() => setShowModal(false)}
                  style={{ padding: '10px 20px' }}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

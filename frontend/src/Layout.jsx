import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { api } from './api';

export default function Layout({ children, status }) {
  const [showModal, setShowModal]         = useState(false);
  const [projects, setProjects]           = useState([]);
  const [selProject, setSelProject]       = useState(null);
  const [newProjName, setNewProjName]     = useState('');
  const [mode, setMode]                   = useState('normal');
  const [message, setMessage]             = useState('');
  const [creating, setCreating]           = useState(false);
  const [error, setError]                 = useState('');
  const [sidebarKey, setSidebarKey]       = useState(0);
  const navigate                          = useNavigate();

  const openModal = async () => {
    setError('');
    setMessage('');
    const ps = await api.getProjects().catch(() => []);
    setProjects(ps);
    setSelProject(ps[0] ?? null);
    setShowModal(true);
  };

  const createSession = async (e) => {
    e.preventDefault();
    if (!message.trim()) { setError('Message is required'); return; }
    setCreating(true);
    setError('');
    try {
      let proj = selProject;
      if (!proj) {
        // Create new project on-the-fly
        const name = newProjName.trim() || `project_${Date.now()}`;
        proj = await api.createProject(name);
        setSidebarKey(k => k + 1); // refresh sidebar
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

  return (
    <div className="flex h-screen bg-black text-g-bright font-term crt overflow-hidden">
      <Sidebar onNewSession={openModal} refreshKey={sidebarKey} />

      {/* Main area */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {children}

        {/* Status bar */}
        <div className="shrink-0 border-t border-g-border px-4 py-1 text-g-dim text-base flex items-center gap-2">
          <span className="text-g-bright">{'>'}</span>
          <span className="truncate">{status || 'ready | api: ONLINE'}</span>
          <span className="ml-auto shrink-0 text-xs opacity-40">
            {new Date().toLocaleTimeString('en-US', { hour12: false })}
          </span>
        </div>
      </div>

      {/* ── New Session Modal ── */}
      {showModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="border border-g-bright glow-box bg-black w-full max-w-lg p-6">
            <div className="text-g-bright text-xl mb-5">// NEW SESSION</div>

            <form onSubmit={createSession} className="space-y-4">
              {/* Project picker */}
              <div>
                <div className="text-g-dim text-sm mb-1">{'>'} project</div>
                {projects.length > 0 ? (
                  <select
                    className="w-full bg-g-dark border border-g-border text-g-bright font-term text-base px-3 py-1 outline-none focus:border-g-bright"
                    value={selProject?.id ?? ''}
                    onChange={e => {
                      const p = projects.find(x => x.id === parseInt(e.target.value));
                      setSelProject(p ?? null);
                    }}
                  >
                    <option value="">— create new project —</option>
                    {projects.map(p => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                ) : null}

                {(!selProject) && (
                  <input
                    className="tinput mt-2 w-full"
                    placeholder="new project name..."
                    value={newProjName}
                    onChange={e => setNewProjName(e.target.value)}
                  />
                )}
              </div>

              {/* Mode */}
              <div>
                <div className="text-g-dim text-sm mb-1">{'>'} mode</div>
                <div className="flex gap-2">
                  {['normal', 'hardcore'].map(m => (
                    <button
                      key={m}
                      type="button"
                      className={`tbtn ${mode === m ? 'active' : ''}`}
                      onClick={() => setMode(m)}
                    >
                      {m.toUpperCase()}
                    </button>
                  ))}
                </div>
                <div className="text-g-dim text-xs mt-1">
                  {mode === 'normal'
                    ? 'normal: execute immediately'
                    : 'hardcore: gather requirements first'}
                </div>
              </div>

              {/* Message */}
              <div>
                <div className="text-g-dim text-sm mb-1">{'>'} describe what to build</div>
                <textarea
                  autoFocus
                  className="w-full bg-g-dark border border-g-border text-g-bright font-term text-base px-3 py-2 outline-none focus:border-g-bright resize-none"
                  placeholder="Build a REST API for a todo app with user authentication..."
                  rows={4}
                  value={message}
                  onChange={e => setMessage(e.target.value)}
                />
              </div>

              {error && (
                <div className="text-red-400 text-base">{'>'} ERROR: {error}</div>
              )}

              <div className="flex gap-3 pt-1">
                <button type="submit" className="tbtn" disabled={creating}>
                  {creating ? 'LAUNCHING...' : 'START SESSION'}
                </button>
                <button
                  type="button"
                  className="tbtn"
                  onClick={() => setShowModal(false)}
                >
                  CANCEL
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

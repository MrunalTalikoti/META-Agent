import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from './Sidebar';
import { api } from './api';

const MODE_INFO = {
  normal: {
    label:   'NORMAL',
    hint:    'Execute immediately — agents run in parallel once requirements are clear.',
    agents:  ['code_generator', 'api_designer', 'database_schema', 'testing_agent',
              'frontend_generator', 'devops', 'security_auditor', 'documentation_agent', 'performance_optimizer'],
  },
  hardcore: {
    label:   'HARDCORE',
    hint:    'Requirements first — agent asks clarifying questions before executing.',
    agents:  ['requirements_gatherer', '→ all agents'],
  },
};

export default function Layout({ children, status }) {
  const [showModal, setShowModal]       = useState(false);
  const [projects, setProjects]         = useState([]);
  const [selProject, setSelProject]     = useState(null);
  const [newProjName, setNewProjName]   = useState('');
  const [newProjDesc, setNewProjDesc]   = useState('');
  const [mode, setMode]                 = useState('normal');
  const [message, setMessage]           = useState('');
  const [creating, setCreating]         = useState(false);
  const [error, setError]               = useState('');
  const [sidebarKey, setSidebarKey]     = useState(0);
  const navigate                        = useNavigate();

  const openModal = async () => {
    setError('');
    setMessage('');
    setNewProjName('');
    setNewProjDesc('');
    setMode('normal');
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

      {/* ── New Session Modal ──────────────────────────────────────────────── */}
      {showModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="border border-g-bright glow-box bg-black w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
            <div className="text-g-bright text-xl mb-5">// NEW SESSION</div>

            <form onSubmit={createSession} className="space-y-4">

              {/* Project picker */}
              <div>
                <div className="text-g-dim text-sm mb-1">{'>'} project</div>
                {projects.length > 0 && (
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
                )}

                {!selProject && (
                  <div className="mt-2 space-y-2">
                    <input
                      className="tinput w-full"
                      placeholder="project name..."
                      value={newProjName}
                      onChange={e => setNewProjName(e.target.value)}
                    />
                    <input
                      className="tinput w-full"
                      placeholder="description (optional)..."
                      value={newProjDesc}
                      onChange={e => setNewProjDesc(e.target.value)}
                    />
                  </div>
                )}
              </div>

              {/* Mode selector */}
              <div>
                <div className="text-g-dim text-sm mb-1">{'>'} mode</div>
                <div className="flex gap-2 mb-2">
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
                <div className="text-g-dim text-xs leading-snug">{modeInfo.hint}</div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {modeInfo.agents.map(a => (
                    <span key={a} className="border border-g-border text-g-dim text-xs px-1.5 py-0.5">
                      {a.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>

              {/* Request message */}
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
                <div className="text-g-dim text-xs mt-1 text-right">
                  {message.length}/5000
                </div>
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

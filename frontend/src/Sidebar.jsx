import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from './api';
import { useAuth } from './AuthContext';

const TIER_COLOR = {
  free:       'text-g-dim',
  pro:        'text-yellow-400',
  enterprise: 'text-g-bright',
};

function firstUserMessage(conv) {
  const msg = (conv.messages ?? []).find(m => m.role === 'user');
  return msg?.content ?? `${conv.mode}_${conv.id}`;
}

export default function Sidebar({ onNewSession, refreshKey }) {
  const [projects, setProjects]   = useState([]);
  const [expanded, setExpanded]   = useState(null);
  const [convs, setConvs]         = useState({});
  const [search, setSearch]       = useState('');
  const { user, logout }          = useAuth();
  const navigate                  = useNavigate();

  useEffect(() => {
    api.getProjects().then(setProjects).catch(() => {});
  }, [refreshKey]);

  const toggle = async (proj) => {
    if (expanded === proj.id) { setExpanded(null); return; }
    setExpanded(proj.id);
    if (!convs[proj.id]) {
      const cs = await api.getConversations(proj.id).catch(() => []);
      setConvs(prev => ({ ...prev, [proj.id]: cs }));
    }
  };

  const deleteConv = async (e, convId, projId) => {
    e.stopPropagation();
    if (!window.confirm('Delete this session?')) return;
    await api.deleteConversation(convId).catch(() => {});
    setConvs(prev => ({
      ...prev,
      [projId]: (prev[projId] ?? []).filter(c => c.id !== convId),
    }));
  };

  const filteredProjects = search
    ? projects.filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
    : projects;

  const statusDot = (status) => {
    if (status === 'completed') return <span className="text-g-bright">✓</span>;
    if (status === 'executing') return <span className="text-g-bright animate-blink">▶</span>;
    return <span className="text-g-dim">○</span>;
  };

  return (
    <aside className="flex flex-col h-full bg-black border-r border-g-border font-term select-none w-64 shrink-0">

      {/* New Session */}
      <div className="p-3 border-b border-g-border">
        <button className="tbtn w-full" onClick={onNewSession}>
          + NEW SESSION
        </button>
      </div>

      {/* Search */}
      <div className="px-3 py-2 border-b border-g-border">
        <div className="flex items-center gap-2 border border-g-border px-2 py-1">
          <span className="text-g-dim text-sm">[SEARCH]</span>
          <input
            className="tinput text-base flex-1"
            placeholder="find project"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Project + conversation list */}
      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        <div className="text-g-dim text-sm mb-2">// RECENT SESSIONS</div>

        {filteredProjects.length === 0 && (
          <div className="text-g-dim text-sm px-2">no projects yet</div>
        )}

        {filteredProjects.map(proj => (
          <div key={proj.id}>
            <button
              onClick={() => toggle(proj)}
              className="w-full text-left flex items-center gap-2 px-2 py-0.5 hover:bg-g-dark text-g-bright text-base transition-colors"
            >
              <span className="text-g-dim shrink-0">{expanded === proj.id ? '▼' : '>'}</span>
              <span className="truncate flex-1">
                {proj.name.toLowerCase().replace(/\s+/g, '_')}
              </span>
              {convs[proj.id] && (
                <span className="text-g-dim text-xs shrink-0">
                  ({convs[proj.id].length})
                </span>
              )}
            </button>

            {expanded === proj.id && (
              <div className="pl-5 space-y-0.5 mt-0.5">
                {(convs[proj.id] || []).length === 0 && (
                  <div className="text-g-dim text-xs px-2 py-1">no sessions</div>
                )}
                {(convs[proj.id] || []).map(c => {
                  const label = firstUserMessage(c);
                  return (
                    <div key={c.id} className="flex items-center group">
                      <button
                        onClick={() => navigate(`/c/${c.id}`)}
                        className="flex-1 text-left flex items-center gap-2 px-2 py-0.5 text-g-dim hover:text-g-bright hover:bg-g-dark text-sm transition-colors min-w-0"
                      >
                        <span className="shrink-0">{statusDot(c.status)}</span>
                        <span className="truncate">{label.slice(0, 28)}{label.length > 28 ? '…' : ''}</span>
                      </button>
                      <button
                        onClick={e => deleteConv(e, c.id, proj.id)}
                        className="hidden group-hover:block shrink-0 text-g-dim hover:text-red-400 text-xs px-1.5 py-0.5 transition-colors"
                        title="Delete session"
                      >
                        ✕
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Bottom nav */}
      <div className="border-t border-g-border p-3 space-y-1 text-base">
        <button
          onClick={() => navigate('/metrics')}
          className="w-full text-left flex items-center gap-2 text-g-dim hover:text-g-bright transition-colors py-0.5"
        >
          <span>{'>'}</span>
          <span>metrics</span>
        </button>
        <button
          onClick={logout}
          className="w-full text-left flex items-center gap-2 text-g-dim hover:text-g-bright transition-colors py-0.5"
        >
          <span>{'>'}</span>
          <span>logout</span>
        </button>
      </div>

      {/* User info strip */}
      {user && (
        <div className="border-t border-g-border px-3 py-2 text-xs space-y-0.5">
          {user.email && (
            <div className="text-g-dim truncate" title={user.email}>
              {user.email}
            </div>
          )}
          <div className="flex items-center gap-2">
            <span className={TIER_COLOR[user.tier] ?? 'text-g-dim'}>
              {(user.tier ?? 'free').toUpperCase()}
            </span>
            {user.requestsToday != null && (
              <span className="text-g-dim">
                · {user.requestsToday} req today
              </span>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}

import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from './api';
import { useAuth } from './AuthContext';

const TIER_BADGE = {
  free:       { label: 'FREE',       color: 'rgba(255,255,255,0.35)' },
  pro:        { label: 'PRO',        color: '#f5c518'                },
  enterprise: { label: 'ENTERPRISE', color: '#fff'                   },
};

function firstUserMessage(conv) {
  const msg = (conv.messages ?? []).find(m => m.role === 'user');
  return msg?.content ?? `session_${conv.id}`;
}

function StatusDot({ status }) {
  if (status === 'completed')
    return <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: '10px' }}>✓</span>;
  if (status === 'executing')
    return <span style={{ color: '#fff', fontSize: '10px' }} className="animate-blink">●</span>;
  return <span style={{ color: 'rgba(255,255,255,0.2)', fontSize: '10px' }}>○</span>;
}

export default function Sidebar({ onNewSession, refreshKey }) {
  const [projects, setProjects] = useState([]);
  const [expanded, setExpanded] = useState(null);
  const [convs, setConvs]       = useState({});
  const [search, setSearch]     = useState('');
  const { user, logout }        = useAuth();
  const navigate                = useNavigate();

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

  const filtered = search
    ? projects.filter(p => p.name.toLowerCase().includes(search.toLowerCase()))
    : projects;

  const tier   = user?.tier ?? 'free';
  const badge  = TIER_BADGE[tier] ?? TIER_BADGE.free;

  return (
    <aside style={{
      width: '240px',
      flexShrink: 0,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: '#0d0d0d',
      borderRight: '1px solid rgba(255,255,255,0.07)',
      userSelect: 'none',
    }}>

      {/* Brand + New Session */}
      <div style={{ padding: '24px 16px 16px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <div style={{
          fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em',
          color: 'rgba(255,255,255,0.35)', textTransform: 'uppercase', marginBottom: '14px',
        }}>
          Meta-Agent
        </div>
        <button
          className="tbtn"
          onClick={onNewSession}
          style={{ width: '100%', padding: '8px 16px', fontSize: '11px' }}
        >
          + New Session
        </button>
      </div>

      {/* Search */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <input
          className="tinput"
          placeholder="Search projects..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{ fontSize: '13px' }}
        />
      </div>

      {/* Project + session list */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 8px' }}>
        <div style={{
          fontSize: '9px', fontWeight: 700, letterSpacing: '0.16em',
          color: 'rgba(255,255,255,0.28)', textTransform: 'uppercase',
          padding: '0 8px', marginBottom: '8px',
        }}>
          Sessions
        </div>

        {filtered.length === 0 && (
          <div style={{ padding: '8px', color: 'rgba(255,255,255,0.25)', fontSize: '12px' }}>
            No projects yet
          </div>
        )}

        {filtered.map(proj => (
          <div key={proj.id}>
            <button
              onClick={() => toggle(proj)}
              style={{
                width: '100%', textAlign: 'left', display: 'flex', alignItems: 'center',
                gap: '6px', padding: '5px 8px', background: 'transparent', border: 'none',
                color: 'rgba(255,255,255,0.75)', fontSize: '13px', cursor: 'pointer',
                borderRadius: '3px', transition: 'background 0.1s',
              }}
              onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.05)'}
              onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
            >
              <span style={{ color: 'rgba(255,255,255,0.3)', fontSize: '10px', flexShrink: 0 }}>
                {expanded === proj.id ? '▾' : '›'}
              </span>
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {proj.name}
              </span>
              {convs[proj.id] && (
                <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: '11px', flexShrink: 0 }}>
                  {convs[proj.id].length}
                </span>
              )}
            </button>

            {expanded === proj.id && (
              <div style={{ paddingLeft: '20px' }}>
                {(convs[proj.id] || []).length === 0 && (
                  <div style={{ padding: '4px 8px', color: 'rgba(255,255,255,0.2)', fontSize: '11px' }}>
                    No sessions
                  </div>
                )}
                {(convs[proj.id] || []).map(c => {
                  const label = firstUserMessage(c);
                  return (
                    <div key={c.id} style={{ display: 'flex', alignItems: 'center', position: 'relative' }}
                      className="group"
                    >
                      <button
                        onClick={() => navigate(`/c/${c.id}`)}
                        style={{
                          flex: 1, textAlign: 'left', display: 'flex', alignItems: 'center',
                          gap: '6px', padding: '4px 8px', background: 'transparent', border: 'none',
                          color: 'rgba(255,255,255,0.45)', fontSize: '12px', cursor: 'pointer',
                          borderRadius: '3px', minWidth: 0, transition: 'color 0.1s',
                        }}
                        onMouseEnter={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.8)')}
                        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.45)')}
                      >
                        <StatusDot status={c.status} />
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {label.slice(0, 26)}{label.length > 26 ? '…' : ''}
                        </span>
                      </button>
                      <button
                        onClick={e => deleteConv(e, c.id, proj.id)}
                        style={{
                          background: 'none', border: 'none', color: 'rgba(255,255,255,0.2)',
                          fontSize: '11px', padding: '4px 6px', cursor: 'pointer',
                          opacity: 0, transition: 'opacity 0.1s, color 0.1s',
                        }}
                        onMouseEnter={e => { e.currentTarget.style.color = '#ff6b6b'; e.currentTarget.style.opacity = 1; }}
                        onMouseLeave={e => { e.currentTarget.style.color = 'rgba(255,255,255,0.2)'; e.currentTarget.style.opacity = 0; }}
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

      {/* Nav links */}
      <div style={{ padding: '8px', borderTop: '1px solid rgba(255,255,255,0.07)' }}>
        {[
          { label: 'Usage Metrics', action: () => navigate('/metrics') },
          { label: 'Sign Out',      action: logout },
        ].map(({ label, action }) => (
          <button
            key={label}
            onClick={action}
            style={{
              width: '100%', textAlign: 'left', padding: '7px 8px',
              background: 'transparent', border: 'none',
              color: 'rgba(255,255,255,0.4)', fontSize: '12px',
              fontWeight: 500, cursor: 'pointer', borderRadius: '3px',
              transition: 'color 0.1s',
              fontFamily: 'inherit',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
          >
            {label}
          </button>
        ))}
      </div>

      {/* User strip */}
      {user && (
        <div style={{ padding: '10px 16px', borderTop: '1px solid rgba(255,255,255,0.07)' }}>
          {user.email && (
            <div style={{
              fontSize: '11px', color: 'rgba(255,255,255,0.35)',
              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              marginBottom: '4px',
            }} title={user.email}>
              {user.email}
            </div>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '9px', fontWeight: 700, letterSpacing: '0.12em', color: badge.color }}>
              {badge.label}
            </span>
            {user.requestsToday != null && (
              <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.25)' }}>
                {user.requestsToday} req today
              </span>
            )}
          </div>
        </div>
      )}
    </aside>
  );
}

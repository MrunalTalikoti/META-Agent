import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Layout from './Layout';
import FileBrowser from './FileBrowser';
import { api } from './api';

function firstUserMessage(conv) {
  const msg = (conv.messages ?? []).find(m => m.role === 'user');
  return msg?.content ?? `session_${conv.id}`;
}

function StatusDot({ status }) {
  const color =
    status === 'completed' ? 'rgba(255,255,255,0.5)' :
    status === 'executing' ? '#fff' :
    'rgba(255,255,255,0.18)';
  return (
    <span style={{
      display: 'inline-block', width: '6px', height: '6px',
      borderRadius: '50%', background: color, flexShrink: 0,
    }} className={status === 'executing' ? 'animate-blink' : ''} />
  );
}

// ── Inline-editable project tab ───────────────────────────────────────────────
function ProjectTab({ proj, isSelected, onClick, onRename, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [name, setName]       = useState(proj.name);
  const [saving, setSaving]   = useState(false);
  const inputRef              = useRef(null);

  useEffect(() => { if (editing) inputRef.current?.focus(); }, [editing]);

  const commit = async () => {
    const trimmed = name.trim();
    if (!trimmed || trimmed === proj.name) { setEditing(false); setName(proj.name); return; }
    setSaving(true);
    try { await onRename(proj.id, trimmed); } catch { setName(proj.name); }
    setSaving(false); setEditing(false);
  };

  if (editing) {
    return (
      <input
        ref={inputRef}
        style={{
          background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.25)',
          color: '#fff', fontFamily: 'inherit', fontSize: '12px', padding: '4px 10px',
          outline: 'none', borderRadius: '2px', width: '120px',
        }}
        value={name}
        onChange={e => setName(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') commit(); if (e.key === 'Escape') { setEditing(false); setName(proj.name); } }}
        onBlur={commit}
        disabled={saving}
      />
    );
  }

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '2px', position: 'relative' }}>
      <button
        onClick={onClick}
        style={{
          padding: '5px 14px', fontFamily: 'inherit', fontSize: '12px', fontWeight: 500,
          border: isSelected ? '1px solid rgba(255,255,255,0.35)' : '1px solid rgba(255,255,255,0.1)',
          background: isSelected ? 'rgba(255,255,255,0.06)' : 'transparent',
          color: isSelected ? '#fff' : 'rgba(255,255,255,0.45)',
          cursor: 'pointer', borderRadius: '2px', transition: 'all 0.12s', whiteSpace: 'nowrap',
        }}
        onMouseEnter={e => { if (!isSelected) e.currentTarget.style.color = 'rgba(255,255,255,0.8)'; }}
        onMouseLeave={e => { if (!isSelected) e.currentTarget.style.color = 'rgba(255,255,255,0.45)'; }}
      >
        {proj.name}
      </button>
      {isSelected && (
        <>
          <button
            onClick={e => { e.stopPropagation(); setEditing(true); }}
            title="Rename"
            style={{
              background: 'none', border: 'none', color: 'rgba(255,255,255,0.3)',
              fontSize: '12px', padding: '4px 4px', cursor: 'pointer',
              fontFamily: 'inherit', transition: 'color 0.1s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
          >
            ✎
          </button>
          <button
            onClick={e => { e.stopPropagation(); onDelete(proj.id, proj.name); }}
            title="Delete project"
            style={{
              background: 'none', border: 'none', color: 'rgba(255,255,255,0.3)',
              fontSize: '11px', padding: '4px 4px', cursor: 'pointer',
              fontFamily: 'inherit', transition: 'color 0.1s',
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#ff6b6b')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.3)')}
          >
            ✕
          </button>
        </>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function Dashboard() {
  const [projects, setProjects]   = useState([]);
  const [selected, setSelected]   = useState(null);
  const [convs, setConvs]         = useState([]);
  const [exporting, setExporting] = useState(false);
  const [showFiles, setShowFiles] = useState(false);
  const [searchParams]            = useSearchParams();
  const navigate                  = useNavigate();

  useEffect(() => {
    api.getProjects().then(ps => {
      setProjects(ps);
      const pid    = searchParams.get('project');
      const target = pid ? ps.find(p => p.id === parseInt(pid)) : ps[0];
      if (target) selectProject(target, ps);
    }).catch(() => {});
  }, []);

  const selectProject = async (proj, list = projects) => {
    setSelected(proj);
    const cs = await api.getConversations(proj.id).catch(() => []);
    setConvs(cs);
  };

  const handleRename = async (id, newName) => {
    const updated = await api.updateProject(id, { name: newName });
    setProjects(prev => prev.map(p => p.id === id ? { ...p, name: updated.name ?? newName } : p));
    if (selected?.id === id) setSelected(s => ({ ...s, name: updated.name ?? newName }));
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete project "${name}" and all its sessions?`)) return;
    await api.deleteProject(id);
    const remaining = projects.filter(p => p.id !== id);
    setProjects(remaining);
    if (selected?.id === id) {
      const next = remaining[0] ?? null;
      if (next) selectProject(next, remaining);
      else { setSelected(null); setConvs([]); }
    }
  };

  const handleExport = async () => {
    if (!selected) return;
    setExporting(true);
    try {
      const res  = await api.exportProject(selected.id);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `${selected.name.replace(/\s+/g, '_')}_project.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      alert(err.message);
    } finally {
      setExporting(false);
    }
  };

  const statusText = selected
    ? `Project: ${selected.name} — Claude 3.5 Sonnet — API Online`
    : 'Ready — Claude 3.5 Sonnet — API Online';

  return (
    <Layout status={statusText}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Tab bar */}
        <div style={{
          flexShrink: 0,
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          padding: '10px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
          overflowX: 'auto',
        }}>
          {projects.slice(0, 5).map(p => (
            <ProjectTab
              key={p.id}
              proj={p}
              isSelected={selected?.id === p.id}
              onClick={() => selectProject(p)}
              onRename={handleRename}
              onDelete={handleDelete}
            />
          ))}
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
            {selected && (
              <>
                <button className="tbtn" onClick={() => setShowFiles(true)}>Files</button>
                <button className="tbtn" onClick={handleExport} disabled={exporting}>
                  {exporting ? 'Exporting...' : 'Export ZIP'}
                </button>
              </>
            )}
            <button className="tbtn" onClick={() => navigate('/metrics')}>Metrics</button>
          </div>
        </div>

        {/* Center content */}
        <div style={{
          flex: 1, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          overflowY: 'auto', padding: '40px 24px',
        }}>

          {/* Hero typography */}
          <div style={{ textAlign: 'center', marginBottom: projects.length === 0 ? '48px' : '52px' }}>
            <div
              className="logo-pixel"
              style={{ fontSize: 'clamp(3.5rem, 10vw, 9rem)', marginBottom: '16px', display: 'block' }}
            >
              META-AGENT
            </div>
            <div style={{
              fontSize: '10px', fontWeight: 600, letterSpacing: '0.22em',
              color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase',
            }}>
              AI Orchestration Platform
            </div>
          </div>

          {/* Empty state */}
          {projects.length === 0 && (
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '15px', color: 'rgba(255,255,255,0.4)', marginBottom: '8px' }}>
                No projects yet
              </div>
              <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.22)' }}>
                Click <strong style={{ color: 'rgba(255,255,255,0.5)' }}>+ New Session</strong> in the sidebar to begin
              </div>
            </div>
          )}

          {/* Session list */}
          {selected && (
            <div style={{ width: '100%', maxWidth: '560px' }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px',
              }}>
                <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.3)' }}>
                  {selected.name}
                </span>
                <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)' }}>
                  {convs.length} session{convs.length !== 1 ? 's' : ''}
                </span>
              </div>

              {convs.length === 0 && (
                <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.28)', padding: '4px 0' }}>
                  No sessions yet — start one with + New Session
                </div>
              )}

              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                {convs.map(c => {
                  const label = firstUserMessage(c);
                  return (
                    <button
                      key={c.id}
                      onClick={() => navigate(`/c/${c.id}`)}
                      style={{
                        width: '100%', textAlign: 'left', display: 'flex', alignItems: 'center',
                        gap: '14px', padding: '12px 16px',
                        border: '1px solid rgba(255,255,255,0.07)',
                        background: 'transparent', cursor: 'pointer', borderRadius: '3px',
                        transition: 'border-color 0.12s, background 0.12s', fontFamily: 'inherit',
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.2)';
                        e.currentTarget.style.background  = 'rgba(255,255,255,0.025)';
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.borderColor = 'rgba(255,255,255,0.07)';
                        e.currentTarget.style.background  = 'transparent';
                      }}
                    >
                      <StatusDot status={c.status} />
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{
                          fontSize: '14px', color: 'rgba(255,255,255,0.85)',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          marginBottom: '2px',
                        }}>
                          {label.slice(0, 70)}{label.length > 70 ? '…' : ''}
                        </div>
                        <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.28)', letterSpacing: '0.03em' }}>
                          {c.mode} · session {c.id}
                        </div>
                      </div>
                      <span style={{
                        fontSize: '10px', fontWeight: 600, letterSpacing: '0.08em',
                        textTransform: 'uppercase', flexShrink: 0,
                        color: c.status === 'completed' ? 'rgba(255,255,255,0.45)' :
                               c.status === 'executing' ? '#fff' : 'rgba(255,255,255,0.25)',
                      }}>
                        {c.status.replace(/_/g, ' ')}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

      </div>

      {showFiles && selected && (
        <FileBrowser
          projectId={selected.id}
          projectName={selected.name}
          onClose={() => setShowFiles(false)}
        />
      )}
    </Layout>
  );
}

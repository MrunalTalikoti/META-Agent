import { useState, useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Layout from './Layout';
import FileBrowser from './FileBrowser';
import { api } from './api';

function firstUserMessage(conv) {
  const msg = (conv.messages ?? []).find(m => m.role === 'user');
  return msg?.content ?? `${conv.mode}_session_${conv.id}`;
}

// ── Inline-editable project name ──────────────────────────────────────────────
function ProjectTab({ proj, isSelected, onClick, onRename, onDelete }) {
  const [editing, setEditing]   = useState(false);
  const [name, setName]         = useState(proj.name);
  const [saving, setSaving]     = useState(false);
  const inputRef                = useRef(null);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const commit = async () => {
    const trimmed = name.trim();
    if (!trimmed || trimmed === proj.name) { setEditing(false); setName(proj.name); return; }
    setSaving(true);
    try {
      await onRename(proj.id, trimmed);
    } catch { setName(proj.name); }
    setSaving(false);
    setEditing(false);
  };

  if (editing) {
    return (
      <div className="flex items-center border border-g-bright">
        <input
          ref={inputRef}
          className="tinput px-2 py-0.5 text-sm w-32"
          value={name}
          onChange={e => setName(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') commit();
            if (e.key === 'Escape') { setEditing(false); setName(proj.name); }
          }}
          onBlur={commit}
          disabled={saving}
        />
      </div>
    );
  }

  return (
    <div className="flex items-center gap-0.5 group">
      <button
        className={`tbtn ${isSelected ? 'active' : ''}`}
        onClick={onClick}
      >
        {proj.name.toLowerCase().replace(/\s+/g, '_')}
      </button>
      <button
        className="hidden group-hover:inline-flex tbtn text-xs px-1.5 opacity-60 hover:opacity-100"
        onClick={e => { e.stopPropagation(); setEditing(true); }}
        title="Rename"
      >
        ✎
      </button>
      <button
        className="hidden group-hover:inline-flex tbtn text-xs px-1.5 opacity-60 hover:opacity-100"
        onClick={e => { e.stopPropagation(); onDelete(proj.id, proj.name); }}
        title="Delete project"
      >
        ✕
      </button>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
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
      const pid = searchParams.get('project');
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
      const res = await api.exportProject(selected.id);
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
    ? `project: ${selected.name.toLowerCase()} | model: claude-3-5-sonnet | api: ONLINE`
    : 'ready | model: claude-3-5-sonnet | api: ONLINE | session: none';

  const statusDot = (status) => {
    if (status === 'completed') return <span className="text-g-bright">✓</span>;
    if (status === 'executing') return <span className="text-g-bright animate-blink">▶</span>;
    return <span className="text-g-dim">○</span>;
  };

  return (
    <Layout status={statusText}>
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Top action bar */}
        <div className="shrink-0 border-b border-g-border px-4 py-2 flex items-center gap-2 overflow-x-auto">
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
          <div className="ml-auto flex items-center gap-2 shrink-0">
            {selected && (
              <>
                <button
                  className="tbtn"
                  onClick={() => setShowFiles(true)}
                >
                  FILES
                </button>
                <button
                  className="tbtn"
                  onClick={handleExport}
                  disabled={exporting}
                >
                  {exporting ? 'EXPORTING...' : 'EXPORT_ZIP'}
                </button>
              </>
            )}
            <button className="tbtn" onClick={() => navigate('/metrics')}>
              view_logs
            </button>
          </div>
        </div>

        {/* Center: Logo + project info */}
        <div className="flex-1 flex flex-col items-center justify-center overflow-auto p-6">
          <div
            className="logo-pixel text-center mb-4"
            style={{ fontSize: 'clamp(0.8rem, 2.2vw, 1.5rem)' }}
          >
            META-AGENT
          </div>
          <div className="text-g-dim text-lg mb-8">
            ai orchestration platform v0.2.0
          </div>

          {projects.length === 0 ? (
            <div className="text-g-dim text-base text-center animate-pulse">
              {'>'} no projects yet — click [ + NEW SESSION ] to begin
            </div>
          ) : (
            <div className="w-full max-w-lg space-y-1">
              {selected && (
                <>
                  <div className="text-g-dim text-sm mb-2 flex items-center gap-3">
                    <span>
                      {'>'} sessions for{' '}
                      <span className="text-g-bright">
                        {selected.name.toLowerCase().replace(/\s+/g, '_')}
                      </span>
                    </span>
                    <span className="text-g-dim opacity-60">({convs.length})</span>
                  </div>
                  {convs.length === 0 && (
                    <div className="text-g-dim text-sm px-2">
                      no sessions yet — start one with [ + NEW SESSION ]
                    </div>
                  )}
                  {convs.map(c => (
                    <button
                      key={c.id}
                      onClick={() => navigate(`/c/${c.id}`)}
                      className="w-full text-left flex items-center gap-3 px-3 py-1.5 border border-g-border hover:border-g-bright hover:bg-g-dark transition-colors"
                    >
                      <span className="shrink-0">{statusDot(c.status)}</span>
                      <div className="flex-1 min-w-0">
                        <div className="text-g-bright truncate text-base">
                          {firstUserMessage(c).slice(0, 60)}
                          {firstUserMessage(c).length > 60 ? '…' : ''}
                        </div>
                        <div className="text-g-dim text-sm">
                          {c.mode} · session_{c.id}
                        </div>
                      </div>
                      <span className="text-g-dim text-sm shrink-0">
                        {c.status.replace(/_/g, ' ')}
                      </span>
                    </button>
                  ))}
                </>
              )}
            </div>
          )}
        </div>

        {/* Status line */}
        <div className="shrink-0 px-4 py-1 border-t border-g-border text-g-dim text-base flex items-center gap-2">
          <span className="text-g-bright">{'>'}</span>
          <span>
            ready | model: claude-3-5-sonnet |{' '}
            <span className="text-g-bright">api: ONLINE</span> | project:{' '}
            {selected?.name.toLowerCase() ?? 'none'}
          </span>
        </div>
      </div>

      {/* File browser modal */}
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

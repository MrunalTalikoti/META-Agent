import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import Layout from './Layout';
import { api } from './api';

export default function Dashboard() {
  const [projects, setProjects]         = useState([]);
  const [selected, setSelected]         = useState(null);
  const [convs, setConvs]               = useState([]);
  const [exporting, setExporting]       = useState(false);
  const [searchParams]                  = useSearchParams();
  const navigate                        = useNavigate();

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

  return (
    <Layout status={statusText}>
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Top action bar */}
        <div className="shrink-0 border-b border-g-border px-4 py-2 flex items-center gap-2 overflow-x-auto">
          {projects.slice(0, 5).map(p => (
            <button
              key={p.id}
              className={`tbtn ${selected?.id === p.id ? 'active' : ''}`}
              onClick={() => selectProject(p)}
            >
              {p.name.toLowerCase().replace(/\s+/g, '_')}
            </button>
          ))}
          {selected && (
            <button
              className="tbtn ml-auto shrink-0"
              onClick={handleExport}
              disabled={exporting}
            >
              {exporting ? 'EXPORTING...' : 'EXPORT_ZIP'}
            </button>
          )}
          <button
            className="tbtn shrink-0"
            onClick={() => navigate('/metrics')}
          >
            view_logs
          </button>
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
              {/* Recent sessions for selected project */}
              {selected && (
                <>
                  <div className="text-g-dim text-sm mb-2">
                    {'>'} sessions for{' '}
                    <span className="text-g-bright">
                      {selected.name.toLowerCase().replace(/\s+/g, '_')}
                    </span>
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
                      <span className={
                        c.status === 'completed' ? 'text-g-bright' :
                        c.status === 'executing' ? 'text-g-bright animate-blink' :
                        'text-g-dim'
                      }>
                        {c.status === 'completed' ? '✓' :
                         c.status === 'executing' ? '▶' : '○'}
                      </span>
                      <span className="text-g-bright flex-1 truncate">
                        {c.mode}_session_{c.id}
                      </span>
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

        {/* Status line (above input) */}
        <div className="shrink-0 px-4 py-1 border-t border-g-border text-g-dim text-base flex items-center gap-2">
          <span className="text-g-bright">{'>'}</span>
          <span>
            ready | model: claude-3-5-sonnet |{' '}
            <span className="text-g-bright">api: ONLINE</span> | session:{' '}
            {selected?.name.toLowerCase() ?? 'none'}
          </span>
        </div>
      </div>
    </Layout>
  );
}

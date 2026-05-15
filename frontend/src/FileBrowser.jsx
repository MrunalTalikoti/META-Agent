import { useState, useEffect } from 'react';
import { api } from './api';

const AGENT_LABELS = {
  code_generator:        'Backend Code',
  api_designer:          'API Spec',
  database_schema:       'Database',
  testing_agent:         'Tests',
  documentation_agent:   'Documentation',
  frontend_generator:    'Frontend',
  devops:                'DevOps',
  security_auditor:      'Security',
  performance_optimizer: 'Reports',
};

function fmtSize(bytes) {
  if (!bytes) return '';
  if (bytes < 1024)        return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export default function FileBrowser({ projectId, projectName, onClose }) {
  const [data, setData]               = useState(null);
  const [error, setError]             = useState('');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api.listProjectFiles(projectId).then(setData).catch(e => setError(e.message));
  }, [projectId]);

  const grouped = (data?.files ?? []).reduce((acc, f) => {
    const label = AGENT_LABELS[f.agent] ?? f.agent ?? 'Other';
    if (!acc[label]) acc[label] = [];
    acc[label].push(f);
    return acc;
  }, {});

  const total = data?.files?.length ?? 0;

  const download = async () => {
    setDownloading(true); setError('');
    try {
      const res = await api.exportProject(projectId);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement('a');
      a.href     = url;
      a.download = `${(projectName || 'project').replace(/\s+/g, '_')}_project.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
        backdropFilter: 'blur(4px)', display: 'flex', alignItems: 'center',
        justifyContent: 'center', zIndex: 50, padding: '16px',
      }}
      onClick={e => e.target === e.currentTarget && onClose()}
    >
      <div style={{
        background: '#0d0d0d', border: '1px solid rgba(255,255,255,0.1)',
        width: '100%', maxWidth: '480px', padding: '32px 36px',
        maxHeight: '80vh', display: 'flex', flexDirection: 'column',
      }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '24px' }}>
          <div>
            <div style={{
              fontSize: '9px', fontWeight: 700, letterSpacing: '0.18em',
              color: 'rgba(255,255,255,0.3)', textTransform: 'uppercase', marginBottom: '6px',
            }}>
              Project Files
            </div>
            <div style={{ fontSize: '20px', fontWeight: 200, letterSpacing: '-0.01em' }}>
              {projectName ?? 'Project'}
            </div>
            {data && (
              <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.3)', marginTop: '4px' }}>
                {total} {total === 1 ? 'file' : 'files'}
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'none', border: 'none', color: 'rgba(255,255,255,0.35)',
              fontSize: '18px', cursor: 'pointer', padding: '0', fontFamily: 'inherit',
              transition: 'color 0.1s', lineHeight: 1,
            }}
            onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
            onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.35)')}
          >
            ✕
          </button>
        </div>

        {/* Loading */}
        {!data && !error && (
          <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.3)', letterSpacing: '0.06em' }} className="animate-pulse">
            Scanning files...
          </div>
        )}

        {/* Error */}
        {error && <div style={{ color: '#ff6b6b', fontSize: '13px' }}>{error}</div>}

        {/* File list */}
        {data && (
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            {total === 0 && (
              <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.3)' }}>
                No exportable files found
              </div>
            )}
            {Object.entries(grouped).map(([cat, files]) => (
              <div key={cat} style={{ marginBottom: '20px' }}>
                <div style={{
                  fontSize: '9px', fontWeight: 700, letterSpacing: '0.18em',
                  color: 'rgba(255,255,255,0.28)', textTransform: 'uppercase', marginBottom: '8px',
                }}>
                  {cat}
                </div>
                {files.map((f, i) => (
                  <div key={i} style={{
                    display: 'flex', alignItems: 'center', gap: '10px',
                    padding: '6px 0', borderBottom: '1px solid rgba(255,255,255,0.04)',
                  }}>
                    <span style={{ color: 'rgba(255,255,255,0.15)', fontSize: '12px', flexShrink: 0 }}>—</span>
                    <span style={{
                      fontSize: '13px', fontFamily: '"Courier New", monospace',
                      color: 'rgba(255,255,255,0.75)', flex: 1,
                      overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                    }}>
                      {f.filename}
                    </span>
                    {f.size_bytes != null && (
                      <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.25)', flexShrink: 0 }}>
                        {fmtSize(f.size_bytes)}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Download */}
        {data && total > 0 && (
          <div style={{
            marginTop: '20px', paddingTop: '20px',
            borderTop: '1px solid rgba(255,255,255,0.07)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.3)' }}>
              {total} files → .zip
            </span>
            <button
              onClick={download}
              disabled={downloading}
              style={{
                padding: '8px 24px', background: '#fff', color: '#000',
                border: 'none', fontFamily: 'inherit', fontSize: '11px',
                fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase',
                cursor: downloading ? 'not-allowed' : 'pointer',
                opacity: downloading ? 0.5 : 1, borderRadius: '2px',
                transition: 'opacity 0.15s',
              }}
            >
              {downloading ? 'Downloading...' : 'Download ZIP'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

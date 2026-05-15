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
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

export default function FileBrowser({ projectId, projectName, onClose }) {
  const [data, setData]             = useState(null);
  const [error, setError]           = useState('');
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    api.listProjectFiles(projectId)
      .then(setData)
      .catch(e => setError(e.message));
  }, [projectId]);

  const grouped = (data?.files ?? []).reduce((acc, f) => {
    const label = AGENT_LABELS[f.agent] ?? f.agent ?? 'Other';
    if (!acc[label]) acc[label] = [];
    acc[label].push(f);
    return acc;
  }, {});

  const total = data?.files?.length ?? 0;

  const download = async () => {
    setDownloading(true);
    setError('');
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
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="border border-g-bright glow-box bg-black w-full max-w-lg p-6 max-h-[80vh] flex flex-col">

        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <span className="text-g-bright text-xl">// PROJECT FILES</span>
          <button className="tbtn text-sm" onClick={onClose}>✕ CLOSE</button>
        </div>

        {/* Project info */}
        <div className="text-g-dim text-sm mb-3">
          {'>'} {(projectName ?? 'project').toLowerCase().replace(/\s+/g, '_')}
          {data && (
            <span className="text-g-bright ml-2">— {total} {total === 1 ? 'file' : 'files'}</span>
          )}
        </div>

        {/* Loading */}
        {!data && !error && (
          <div className="text-g-dim animate-pulse text-base flex-1">scanning files...</div>
        )}

        {/* Error */}
        {error && (
          <div className="text-red-400 text-base">{'>'} ERROR: {error}</div>
        )}

        {/* File list */}
        {data && (
          <div className="flex-1 overflow-y-auto space-y-3 min-h-0">
            {total === 0 && (
              <div className="text-g-dim text-sm">no exportable files found for this project</div>
            )}
            {Object.entries(grouped).map(([cat, files]) => (
              <div key={cat}>
                <div className="text-g-dim text-xs mb-1 tracking-wider">// {cat.toUpperCase()}</div>
                {files.map((f, i) => (
                  <div key={i} className="flex items-center gap-2 px-2 py-0.5 hover:bg-g-dark text-sm transition-colors">
                    <span className="text-g-dim shrink-0">─</span>
                    <span className="text-g-bright font-mono flex-1 truncate text-sm">{f.filename}</span>
                    {f.size_bytes != null && (
                      <span className="text-g-dim text-xs shrink-0">{fmtSize(f.size_bytes)}</span>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Download button */}
        {data && total > 0 && (
          <div className="mt-4 pt-4 border-t border-g-border flex items-center justify-between">
            <span className="text-g-dim text-sm">
              {total} files → .zip
            </span>
            <button className="tbtn" onClick={download} disabled={downloading}>
              {downloading ? 'DOWNLOADING...' : 'DOWNLOAD_ZIP'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

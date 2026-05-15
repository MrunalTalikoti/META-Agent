import { useState } from 'react';

const AGENT_LABELS = {
  code_generator:        'Code Generator',
  api_designer:          'API Designer',
  database_schema:       'Database Schema',
  testing_agent:         'Testing Agent',
  documentation_agent:   'Documentation',
  requirements_gatherer: 'Requirements Gatherer',
  frontend_generator:    'Frontend Generator',
  devops:                'DevOps',
  security_auditor:      'Security Auditor',
  performance_optimizer: 'Performance Optimizer',
};

export default function ProgressTracker({ tasks }) {
  const [expanded, setExpanded] = useState(null);

  const total = tasks.length;
  const done  = tasks.filter(t => t.status === 'completed' || t.status === 'failed').length;
  const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

  const icon = (status) => {
    switch (status) {
      case 'completed':   return <span className="text-g-bright">✓</span>;
      case 'failed':      return <span className="text-red-400">✗</span>;
      case 'in_progress': return <span className="text-g-bright animate-blink">▶</span>;
      default:            return <span className="text-g-dim">○</span>;
    }
  };

  const rowColor = (status) => {
    switch (status) {
      case 'in_progress': return 'text-g-bright';
      case 'completed':   return 'text-g-bright';
      case 'failed':      return 'text-red-400';
      default:            return 'text-g-dim';
    }
  };

  const statusLabel = (status) => {
    switch (status) {
      case 'in_progress': return <span className="text-g-bright animate-pulse">running</span>;
      case 'completed':   return <span className="text-g-bright">done</span>;
      case 'failed':      return <span className="text-red-400">failed</span>;
      default:            return <span className="text-g-dim">pending</span>;
    }
  };

  return (
    <div className="border-b border-g-border px-4 py-3 shrink-0">
      {/* Header + progress bar */}
      <div className="flex items-center gap-3 mb-2">
        <span className="text-g-dim text-base shrink-0">{'>'} AGENT PIPELINE</span>
        <span className="text-g-dim text-sm shrink-0">{done}/{total}</span>
        <div className="flex-1 h-1 bg-g-dark border border-g-border overflow-hidden">
          <div
            className="h-full bg-g-bright transition-all duration-700"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="text-g-dim text-sm shrink-0">{pct}%</span>
      </div>

      {/* Task rows */}
      <div className="space-y-0.5">
        {tasks.map((t, i) => {
          const label = AGENT_LABELS[t.agent] ?? (t.agent || t.title || 'task');
          const hasDetail = t.description || t.error_message;

          return (
            <div key={t.task_id ?? i}>
              <button
                onClick={() => hasDetail && setExpanded(expanded === i ? null : i)}
                className={`w-full flex items-center gap-3 text-base font-term px-1 py-0.5 transition-colors ${hasDetail ? 'hover:bg-g-dark cursor-pointer' : 'cursor-default'}`}
              >
                <span className="w-4 text-center shrink-0">{icon(t.status)}</span>
                <span className={rowColor(t.status)}>
                  {label.replace(/_/g, ' ')}
                </span>
                <span className="ml-auto shrink-0 text-sm">{statusLabel(t.status)}</span>
                {hasDetail && (
                  <span className="text-g-dim text-xs w-4 text-center shrink-0">
                    {expanded === i ? '▲' : '▼'}
                  </span>
                )}
              </button>

              {expanded === i && (
                <div className="ml-5 pl-3 border-l border-g-border py-1.5 mb-1 space-y-1 text-sm">
                  {t.description && (
                    <div className="text-g-dim leading-snug">{t.description}</div>
                  )}
                  {t.error_message && (
                    <div className="text-red-400">✗ {t.error_message}</div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

import { useState } from 'react';

const AGENT_LABELS = {
  code_generator:        'Code Generator',
  api_designer:          'API Designer',
  database_schema:       'Database Schema',
  testing_agent:         'Testing',
  documentation_agent:   'Documentation',
  requirements_gatherer: 'Requirements',
  frontend_generator:    'Frontend',
  devops:                'DevOps',
  security_auditor:      'Security Audit',
  performance_optimizer: 'Performance',
};

function AgentIcon({ status }) {
  if (status === 'completed')
    return <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: '11px', width: '14px', textAlign: 'center' }}>✓</span>;
  if (status === 'failed')
    return <span style={{ color: '#ff6b6b', fontSize: '11px', width: '14px', textAlign: 'center' }}>✕</span>;
  if (status === 'in_progress')
    return (
      <span className="animate-blink" style={{
        display: 'inline-block', width: '6px', height: '6px',
        borderRadius: '50%', background: '#fff', margin: '0 4px',
      }} />
    );
  return (
    <span style={{
      display: 'inline-block', width: '6px', height: '6px',
      borderRadius: '50%', border: '1px solid rgba(255,255,255,0.2)',
      margin: '0 4px',
    }} />
  );
}

function statusColor(status) {
  if (status === 'in_progress') return '#fff';
  if (status === 'completed')   return 'rgba(255,255,255,0.55)';
  if (status === 'failed')      return '#ff6b6b';
  return 'rgba(255,255,255,0.22)';
}

export default function ProgressTracker({ tasks }) {
  const [expanded, setExpanded] = useState(null);

  const total = tasks.length;
  const done  = tasks.filter(t => t.status === 'completed' || t.status === 'failed').length;
  const pct   = total > 0 ? Math.round((done / total) * 100) : 0;

  return (
    <div style={{
      flexShrink: 0,
      borderBottom: '1px solid rgba(255,255,255,0.07)',
      background: '#080808',
      padding: '14px 20px',
    }}>
      {/* Header + progress bar */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '12px' }}>
        <span style={{
          fontSize: '9px', fontWeight: 700, letterSpacing: '0.18em',
          textTransform: 'uppercase', color: 'rgba(255,255,255,0.3)', flexShrink: 0,
        }}>
          Agent Pipeline
        </span>
        <div style={{
          flex: 1, height: '1px', background: 'rgba(255,255,255,0.06)', borderRadius: '1px', overflow: 'hidden',
        }}>
          <div style={{
            height: '100%', background: '#fff', width: `${pct}%`,
            transition: 'width 0.7s ease', borderRadius: '1px',
          }} />
        </div>
        <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.3)', flexShrink: 0 }}>
          {done}/{total}
        </span>
      </div>

      {/* Task rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
        {tasks.map((t, i) => {
          const label     = AGENT_LABELS[t.agent] ?? (t.agent || t.title || 'Task');
          const hasDetail = t.description || t.error_message;

          return (
            <div key={t.task_id ?? i}>
              <button
                onClick={() => hasDetail && setExpanded(expanded === i ? null : i)}
                style={{
                  width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
                  padding: '5px 0', background: 'none', border: 'none', cursor: hasDetail ? 'pointer' : 'default',
                  fontFamily: 'inherit', textAlign: 'left',
                }}
              >
                <AgentIcon status={t.status} />
                <span style={{ flex: 1, fontSize: '12px', fontWeight: 500, color: statusColor(t.status) }}>
                  {label}
                </span>
                <span style={{
                  fontSize: '10px', fontWeight: 600, letterSpacing: '0.08em', flexShrink: 0,
                  color: t.status === 'in_progress' ? '#fff'    :
                         t.status === 'completed'   ? 'rgba(255,255,255,0.4)' :
                         t.status === 'failed'      ? '#ff6b6b' : 'rgba(255,255,255,0.18)',
                }}>
                  {t.status === 'in_progress' ? 'Running' :
                   t.status === 'completed'   ? 'Done'    :
                   t.status === 'failed'      ? 'Failed'  : 'Pending'}
                </span>
                {hasDetail && (
                  <span style={{ color: 'rgba(255,255,255,0.25)', fontSize: '10px', width: '12px', textAlign: 'center' }}>
                    {expanded === i ? '▲' : '▼'}
                  </span>
                )}
              </button>

              {expanded === i && (
                <div style={{
                  marginLeft: '24px', paddingLeft: '12px',
                  borderLeft: '1px solid rgba(255,255,255,0.08)',
                  paddingTop: '4px', paddingBottom: '8px',
                  display: 'flex', flexDirection: 'column', gap: '4px',
                }}>
                  {t.description && (
                    <div style={{ fontSize: '12px', color: 'rgba(255,255,255,0.4)', lineHeight: '1.5' }}>
                      {t.description}
                    </div>
                  )}
                  {t.error_message && (
                    <div style={{ fontSize: '12px', color: '#ff6b6b' }}>✕ {t.error_message}</div>
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

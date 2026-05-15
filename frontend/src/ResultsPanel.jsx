import { useState } from 'react';

const TABS = [
  { key: 'code',     label: 'Code'      },
  { key: 'tests',    label: 'Tests'     },
  { key: 'api',      label: 'API Spec'  },
  { key: 'schema',   label: 'DB Schema' },
  { key: 'docs',     label: 'Docs'      },
  { key: 'frontend', label: 'Frontend'  },
  { key: 'devops',   label: 'DevOps'    },
];

function extractOutputs(result) {
  if (!result?.results) return { outputs: {}, validations: {} };
  const all = Object.values(result.results);

  const grab = (...keys) => {
    for (const r of all) {
      const out = r?.output ?? {};
      for (const k of keys) {
        if (out[k]) return typeof out[k] === 'string' ? out[k] : JSON.stringify(out[k], null, 2);
      }
    }
    return null;
  };

  const grabValidation = (...keys) => {
    for (const r of all) {
      const out = r?.output ?? {};
      for (const k of keys) {
        if (out[k] && out['_validation']) return out['_validation'];
      }
    }
    return null;
  };

  return {
    outputs: {
      code:     grab('code'),
      tests:    grab('test_code'),
      api:      grab('api_design'),
      schema:   grab('sql_ddl'),
      docs:     grab('documentation'),
      frontend: grab('html', 'jsx', 'frontend_code', 'react_code'),
      devops:   grab('dockerfile', 'docker_compose', 'deployment_config', 'devops_config'),
    },
    validations: {
      code:     grabValidation('code'),
      tests:    grabValidation('test_code'),
      api:      grabValidation('api_design'),
      schema:   grabValidation('sql_ddl'),
      frontend: grabValidation('html', 'jsx', 'frontend_code', 'react_code'),
    },
  };
}

function qualityColor(score) {
  if (score >= 8) return 'rgba(255,255,255,0.8)';
  if (score >= 6) return '#f5c518';
  return '#ff6b6b';
}

export default function ResultsPanel({ result, onShowFiles }) {
  const { outputs, validations } = extractOutputs(result);
  const available   = TABS.filter(t => outputs[t.key]);
  const [active, setActive]       = useState(available[0]?.key ?? 'code');
  const [copied, setCopied]       = useState(false);
  const [showNotes, setShowNotes] = useState(false);

  if (available.length === 0) {
    return (
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'rgba(255,255,255,0.3)', fontSize: '14px' }}>
        No output to display
      </div>
    );
  }

  const content    = outputs[active];
  const validation = validations[active];

  const allIssues = [
    ...(validation?.syntax?.issues ?? []),
    ...(validation?.quality?.suggestions ?? []).map(s => ({ severity: 'suggestion', message: s })),
  ];

  const copy = async () => {
    if (!content) return;
    await navigator.clipboard.writeText(content).catch(() => {});
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

      {/* Summary bar */}
      <div style={{
        flexShrink: 0, padding: '8px 20px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
      }}>
        <span style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: '#fff' }}>
          Execution Complete
        </span>
        <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)' }}>
          {result?.summary?.completed ?? '?'} / {result?.summary?.total ?? '?'} tasks
        </span>
        {(result?.summary?.failed ?? 0) > 0 && (
          <span style={{ fontSize: '12px', color: '#ff6b6b' }}>
            {result.summary.failed} failed
          </span>
        )}
        {onShowFiles && (
          <button className="tbtn" onClick={onShowFiles} style={{ marginLeft: 'auto' }}>
            Files
          </button>
        )}
      </div>

      {/* Tab bar */}
      <div style={{
        flexShrink: 0, display: 'flex', alignItems: 'flex-end',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
        padding: '0 20px', overflowX: 'auto', gap: '0',
      }}>
        {available.map(t => {
          const v      = validations[t.key];
          const isGood = v?.quality?.score >= 6;
          const dot    = v
            ? <span style={{ marginLeft: '5px', fontSize: '6px', color: isGood ? 'rgba(255,255,255,0.5)' : '#ff6b6b' }}>●</span>
            : null;
          const isActive = active === t.key;
          return (
            <button
              key={t.key}
              onClick={() => { setActive(t.key); setShowNotes(false); }}
              style={{
                padding: '10px 16px', background: 'none', border: 'none',
                borderBottom: isActive ? '2px solid #fff' : '2px solid transparent',
                color: isActive ? '#fff' : 'rgba(255,255,255,0.4)',
                fontFamily: 'inherit', fontSize: '12px', fontWeight: isActive ? 600 : 400,
                cursor: 'pointer', whiteSpace: 'nowrap', letterSpacing: '0.02em',
                transition: 'color 0.12s', marginBottom: '-1px',
              }}
              onMouseEnter={e => { if (!isActive) e.currentTarget.style.color = 'rgba(255,255,255,0.75)'; }}
              onMouseLeave={e => { if (!isActive) e.currentTarget.style.color = 'rgba(255,255,255,0.4)'; }}
            >
              {t.label}{dot}
            </button>
          );
        })}
      </div>

      {/* Validation bar */}
      {validation && (
        <div style={{
          flexShrink: 0, padding: '6px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          background: '#0a0a0a', display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap',
        }}>
          <span style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'rgba(255,255,255,0.3)' }}>
            Validation
          </span>
          <span style={{ fontSize: '12px', color: validation.syntax?.passed ? 'rgba(255,255,255,0.7)' : '#ff6b6b' }}>
            Syntax {validation.syntax?.passed ? '✓ ok' : '✕ fail'}
          </span>
          <span style={{ fontSize: '12px', color: qualityColor(validation.quality?.score ?? 0) }}>
            Quality {validation.quality?.score ?? '?'}/10
          </span>
          {validation.quality?.summary && (
            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.3)', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '240px', whiteSpace: 'nowrap' }}>
              {validation.quality.summary}
            </span>
          )}
          {allIssues.length > 0 && (
            <button
              onClick={() => setShowNotes(!showNotes)}
              style={{
                marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer',
                fontSize: '11px', color: '#f5c518', fontFamily: 'inherit',
                transition: 'color 0.1s',
              }}
              onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
              onMouseLeave={e => (e.currentTarget.style.color = '#f5c518')}
            >
              {showNotes ? '▲ Hide' : `▼ ${allIssues.length} note${allIssues.length !== 1 ? 's' : ''}`}
            </button>
          )}
        </div>
      )}

      {/* Expanded notes */}
      {showNotes && allIssues.length > 0 && (
        <div style={{
          flexShrink: 0, padding: '8px 20px',
          borderBottom: '1px solid rgba(255,255,255,0.07)',
          background: '#0a0a0a', maxHeight: '120px', overflowY: 'auto',
          display: 'flex', flexDirection: 'column', gap: '4px',
        }}>
          {allIssues.map((issue, i) => (
            <div key={i} style={{
              fontSize: '12px',
              color: issue.severity === 'error'   ? '#ff6b6b' :
                     issue.severity === 'warning' ? '#f5c518' : 'rgba(255,255,255,0.4)',
            }}>
              [{issue.severity}]{issue.line ? ` line ${issue.line}:` : ''} {issue.message}
            </div>
          ))}
        </div>
      )}

      {/* Code content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {content ? (
          <div style={{ position: 'relative' }}>
            <button
              onClick={copy}
              className="tbtn"
              style={{ position: 'absolute', top: '12px', right: '12px', zIndex: 10 }}
            >
              {copied ? 'Copied ✓' : 'Copy'}
            </button>
            <pre className="code-block" style={{ paddingRight: '80px' }}>{content}</pre>
          </div>
        ) : (
          <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.3)' }}>
            No {active} output in this session
          </div>
        )}
      </div>
    </div>
  );
}

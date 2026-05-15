import { useState } from 'react';

const TABS = [
  { key: 'code',     label: 'CODE'      },
  { key: 'tests',    label: 'TESTS'     },
  { key: 'api',      label: 'API SPEC'  },
  { key: 'schema',   label: 'DB SCHEMA' },
  { key: 'docs',     label: 'DOCS'      },
  { key: 'frontend', label: 'FRONTEND'  },
  { key: 'devops',   label: 'DEVOPS'    },
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

function scoreColor(score) {
  if (score >= 8) return 'text-g-bright';
  if (score >= 6) return 'text-yellow-400';
  return 'text-red-400';
}

export default function ResultsPanel({ result, onShowFiles }) {
  const { outputs, validations } = extractOutputs(result);
  const available = TABS.filter(t => outputs[t.key]);
  const [active, setActive]         = useState(available[0]?.key ?? 'code');
  const [copied, setCopied]         = useState(false);
  const [showNotes, setShowNotes]   = useState(false);

  if (available.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-g-dim text-base">
        {'>'} no output to display
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
    <div className="flex-1 flex flex-col overflow-hidden">

      {/* Summary bar */}
      <div className="shrink-0 px-4 py-1.5 border-b border-g-border text-base flex items-center gap-4 flex-wrap">
        <span className="text-g-bright">{'>'} execution complete</span>
        <span className="text-g-dim">
          tasks: {result?.summary?.completed ?? '?'}/{result?.summary?.total ?? '?'}
        </span>
        {(result?.summary?.failed ?? 0) > 0 && (
          <span className="text-red-400">failed: {result.summary.failed}</span>
        )}
        {onShowFiles && (
          <button className="tbtn text-sm ml-auto" onClick={onShowFiles}>
            FILES
          </button>
        )}
      </div>

      {/* Tab bar */}
      <div className="shrink-0 flex items-end border-b border-g-border px-4 overflow-x-auto">
        {available.map(t => {
          const v = validations[t.key];
          const dot = v
            ? <span className={`ml-1 text-xs ${v.quality?.score >= 6 ? 'text-g-bright' : 'text-red-400'}`}>●</span>
            : null;
          return (
            <button
              key={t.key}
              onClick={() => { setActive(t.key); setShowNotes(false); }}
              className={`
                px-4 py-1.5 font-term text-base border-b-2 whitespace-nowrap transition-colors
                ${active === t.key
                  ? 'border-g-bright text-g-bright'
                  : 'border-transparent text-g-dim hover:text-g-bright'}
              `}
            >
              {t.label}{dot}
            </button>
          );
        })}
      </div>

      {/* Validation bar */}
      {validation && (
        <div className="shrink-0 px-4 py-1 border-b border-g-border bg-g-dark flex items-center gap-4 text-sm flex-wrap">
          <span className="text-g-dim shrink-0">validation:</span>
          <span className={validation.syntax?.passed ? 'text-g-bright' : 'text-red-400'}>
            syntax {validation.syntax?.passed ? '✓ ok' : '✗ fail'}
          </span>
          <span className={scoreColor(validation.quality?.score ?? 0)}>
            quality {validation.quality?.score ?? '?'}/10
          </span>
          {validation.quality?.summary && (
            <span className="text-g-dim truncate max-w-xs hidden sm:inline">
              {validation.quality.summary}
            </span>
          )}
          {allIssues.length > 0 && (
            <button
              className="ml-auto text-yellow-400 text-xs shrink-0 hover:text-g-bright transition-colors"
              onClick={() => setShowNotes(!showNotes)}
            >
              {showNotes ? '▲ hide' : `▼ ${allIssues.length} note(s)`}
            </button>
          )}
        </div>
      )}

      {/* Expanded notes */}
      {showNotes && allIssues.length > 0 && (
        <div className="shrink-0 px-4 py-2 border-b border-g-border bg-g-dark space-y-1 text-sm max-h-28 overflow-y-auto">
          {allIssues.map((issue, i) => (
            <div
              key={i}
              className={
                issue.severity === 'error'      ? 'text-red-400' :
                issue.severity === 'warning'    ? 'text-yellow-400' :
                issue.severity === 'suggestion' ? 'text-g-dim' :
                'text-g-dim'
              }
            >
              [{issue.severity}]{issue.line ? ` line ${issue.line}:` : ''} {issue.message}
            </div>
          ))}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {content ? (
          <div className="relative">
            <button onClick={copy} className="tbtn text-sm absolute top-3 right-3 z-10">
              {copied ? 'COPIED ✓' : 'COPY'}
            </button>
            <pre className="code-block pr-20">{content}</pre>
          </div>
        ) : (
          <div className="text-g-dim text-base">
            {'>'} no {active} output in this session
          </div>
        )}
      </div>
    </div>
  );
}

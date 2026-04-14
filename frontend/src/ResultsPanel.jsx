import { useState } from 'react';

const TABS = [
  { key: 'code',     label: 'CODE'     },
  { key: 'tests',    label: 'TESTS'    },
  { key: 'api',      label: 'API SPEC' },
  { key: 'schema',   label: 'DB SCHEMA'},
  { key: 'docs',     label: 'DOCS'     },
  { key: 'frontend', label: 'FRONTEND' },
  { key: 'devops',   label: 'DEVOPS'   },
];

function extractOutputs(result) {
  if (!result?.results) return {};
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

  return {
    code:     grab('code'),
    tests:    grab('test_code'),
    api:      grab('api_design'),
    schema:   grab('sql_ddl'),
    docs:     grab('documentation'),
    frontend: grab('html', 'jsx', 'frontend_code', 'react_code'),
    devops:   grab('dockerfile', 'docker_compose', 'deployment_config', 'devops_config'),
  };
}

export default function ResultsPanel({ result }) {
  const outputs  = extractOutputs(result);
  const available = TABS.filter(t => outputs[t.key]);
  const [active, setActive]  = useState(available[0]?.key ?? 'code');
  const [copied, setCopied]  = useState(false);

  if (available.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center text-g-dim text-base">
        {'>'} no output to display
      </div>
    );
  }

  const content = outputs[active];

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
        <span className="text-g-bright">
          {'>'} execution complete
        </span>
        <span className="text-g-dim">
          tasks: {result?.summary?.completed ?? '?'}/{result?.summary?.total ?? '?'}
        </span>
        {(result?.summary?.failed ?? 0) > 0 && (
          <span className="text-red-400">
            failed: {result.summary.failed}
          </span>
        )}
      </div>

      {/* Tab bar */}
      <div className="shrink-0 flex items-end border-b border-g-border px-4 gap-0 overflow-x-auto">
        {available.map(t => (
          <button
            key={t.key}
            onClick={() => setActive(t.key)}
            className={`
              px-4 py-1.5 font-term text-base border-b-2 whitespace-nowrap transition-colors
              ${active === t.key
                ? 'border-g-bright text-g-bright'
                : 'border-transparent text-g-dim hover:text-g-bright'}
            `}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {content ? (
          <div className="relative">
            <button
              onClick={copy}
              className="tbtn text-sm absolute top-3 right-3 z-10"
            >
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

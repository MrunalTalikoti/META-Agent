import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from './Layout';
import { api } from './api';

export default function Metrics() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError]     = useState('');
  const navigate              = useNavigate();

  useEffect(() => {
    api.getMetrics()
      .then(setMetrics)
      .catch(e => setError(e.message));
  }, []);

  const rows = metrics
    ? [
        ['USER ID',          metrics.user_id],
        ['TIER',             metrics.tier?.toUpperCase()],
        ['REQUESTS TODAY',   metrics.requests_today],
        ['─────────────',    '────────────'],
        ['TOTAL PROJECTS',   metrics.projects],
        ['TOTAL TASKS',      metrics.tasks?.total],
        ['COMPLETED TASKS',  metrics.tasks?.completed],
        ['FAILED TASKS',     (metrics.tasks?.total ?? 0) - (metrics.tasks?.completed ?? 0)],
        ['SUCCESS RATE',     `${metrics.tasks?.success_rate ?? 0}%`],
        ['─────────────',    '────────────'],
        ['LLM CALLS',        metrics.llm_usage?.total_calls],
        ['TOKENS USED',      metrics.llm_usage?.total_tokens?.toLocaleString()],
        ['EST. COST (USD)',   `$${metrics.llm_usage?.estimated_cost_usd ?? '0.0000'}`],
      ]
    : [];

  return (
    <Layout status="metrics | api: ONLINE">
      <div className="flex-1 overflow-y-auto p-6">

        {/* Header */}
        <div className="flex items-center gap-4 mb-6">
          <button className="tbtn" onClick={() => navigate('/')}>← back</button>
          <span className="text-g-dim text-xl">// USAGE METRICS</span>
        </div>

        {/* Loading */}
        {!metrics && !error && (
          <div className="text-g-dim animate-pulse cursor text-xl">LOADING</div>
        )}

        {/* Error */}
        {error && (
          <div className="text-red-400 text-base">{'>'} ERROR: {error}</div>
        )}

        {/* Metrics table */}
        {metrics && (
          <div className="border border-g-border max-w-xl">
            <div className="border-b border-g-border px-4 py-2 text-g-dim text-sm">
              {'>'} system stats
            </div>
            {rows.map(([label, value], i) => {
              const isDivider = String(label).startsWith('─');
              if (isDivider) {
                return (
                  <div key={i} className="flex border-b border-g-border opacity-30">
                    <div className="w-52 px-4 py-1 text-g-dim text-sm border-r border-g-border">
                      {label}
                    </div>
                    <div className="px-4 py-1 text-g-dim text-sm">{value}</div>
                  </div>
                );
              }
              return (
                <div key={i} className="flex border-b border-g-border last:border-b-0 hover:bg-g-dark transition-colors">
                  <div className="w-52 px-4 py-2 text-g-dim text-base border-r border-g-border shrink-0">
                    {label}
                  </div>
                  <div className="px-4 py-2 text-g-bright text-base flex-1">
                    {value ?? '—'}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Layout>
  );
}

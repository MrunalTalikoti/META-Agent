import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from './Layout';
import { api } from './api';

function Bar({ value, max, color = 'bg-g-bright' }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  return (
    <div className="flex-1 h-2 bg-g-dark border border-g-border overflow-hidden">
      <div className={`h-full ${color} transition-all duration-700`} style={{ width: `${pct}%` }} />
    </div>
  );
}

const DAILY_LIMITS = { free: 10, pro: 100, enterprise: 1000 };

export default function Metrics() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError]     = useState('');
  const navigate              = useNavigate();

  useEffect(() => {
    api.getMetrics()
      .then(setMetrics)
      .catch(e => setError(e.message));
  }, []);

  const tier       = metrics?.tier ?? 'free';
  const dayLimit   = DAILY_LIMITS[tier] ?? 10;
  const reqToday   = metrics?.requests_today ?? 0;
  const successRate = metrics?.tasks?.success_rate ?? 0;
  const totalTasks = metrics?.tasks?.total ?? 0;
  const doneTasks  = metrics?.tasks?.completed ?? 0;
  const cost       = metrics?.llm_usage?.estimated_cost_usd ?? 0;

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

        {metrics && (
          <div className="space-y-6 max-w-xl">

            {/* Account */}
            <div className="border border-g-border">
              <div className="border-b border-g-border px-4 py-2 text-g-dim text-sm">
                {'>'} account
              </div>
              <Row label="USER ID"  value={metrics.user_id} />
              <Row label="TIER"     value={
                <span className={
                  tier === 'enterprise' ? 'text-g-bright' :
                  tier === 'pro'        ? 'text-yellow-400' :
                  'text-g-dim'
                }>{tier.toUpperCase()}</span>
              } />
            </div>

            {/* Daily usage */}
            <div className="border border-g-border">
              <div className="border-b border-g-border px-4 py-2 text-g-dim text-sm">
                {'>'} daily usage
              </div>
              <BarRow
                label="REQUESTS TODAY"
                value={reqToday}
                max={dayLimit}
                suffix={`/ ${dayLimit}`}
                color={reqToday >= dayLimit * 0.9 ? 'bg-red-500' : reqToday >= dayLimit * 0.6 ? 'bg-yellow-500' : 'bg-g-bright'}
              />
            </div>

            {/* Tasks */}
            <div className="border border-g-border">
              <div className="border-b border-g-border px-4 py-2 text-g-dim text-sm">
                {'>'} task stats
              </div>
              <Row label="TOTAL PROJECTS"  value={metrics.projects} />
              <Row label="TOTAL TASKS"     value={totalTasks} />
              <BarRow
                label="COMPLETED"
                value={doneTasks}
                max={totalTasks || 1}
                suffix={`${doneTasks} / ${totalTasks}`}
              />
              <BarRow
                label="SUCCESS RATE"
                value={successRate}
                max={100}
                suffix={`${successRate}%`}
                color={successRate >= 80 ? 'bg-g-bright' : successRate >= 50 ? 'bg-yellow-500' : 'bg-red-500'}
              />
            </div>

            {/* LLM usage */}
            <div className="border border-g-border">
              <div className="border-b border-g-border px-4 py-2 text-g-dim text-sm">
                {'>'} llm usage
              </div>
              <Row label="LLM CALLS"   value={metrics.llm_usage?.total_calls} />
              <Row label="TOKENS USED" value={metrics.llm_usage?.total_tokens?.toLocaleString()} />
              <Row
                label="EST. COST (USD)"
                value={
                  <span className={cost > 1 ? 'text-yellow-400' : 'text-g-bright'}>
                    ${cost}
                  </span>
                }
              />
            </div>

          </div>
        )}
      </div>
    </Layout>
  );
}

function Row({ label, value }) {
  return (
    <div className="flex border-b border-g-border last:border-b-0 hover:bg-g-dark transition-colors">
      <div className="w-52 px-4 py-2 text-g-dim text-base border-r border-g-border shrink-0">
        {label}
      </div>
      <div className="px-4 py-2 text-g-bright text-base flex-1">
        {value ?? '—'}
      </div>
    </div>
  );
}

function BarRow({ label, value, max, suffix, color = 'bg-g-bright' }) {
  return (
    <div className="flex items-center border-b border-g-border last:border-b-0 hover:bg-g-dark transition-colors">
      <div className="w-52 px-4 py-2 text-g-dim text-base border-r border-g-border shrink-0">
        {label}
      </div>
      <div className="px-4 py-2 flex-1 flex items-center gap-3">
        <Bar value={value} max={max} color={color} />
        <span className="text-g-bright text-sm shrink-0">{suffix ?? value}</span>
      </div>
    </div>
  );
}

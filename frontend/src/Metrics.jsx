import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from './Layout';
import { api } from './api';

const DAILY_LIMITS = { free: 10, pro: 100, enterprise: 1000 };

function Bar({ value, max, danger = false, warn = false }) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
  const color = danger ? '#ff6b6b' : warn ? '#f5c518' : 'rgba(255,255,255,0.7)';
  return (
    <div style={{ flex: 1, height: '2px', background: 'rgba(255,255,255,0.08)', borderRadius: '2px', overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${pct}%`, background: color, transition: 'width 0.7s ease', borderRadius: '2px' }} />
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginBottom: '32px' }}>
      <div style={{
        fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em',
        textTransform: 'uppercase', color: 'rgba(255,255,255,0.28)',
        marginBottom: '12px', paddingBottom: '8px',
        borderBottom: '1px solid rgba(255,255,255,0.07)',
      }}>
        {title}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
        {children}
      </div>
    </div>
  );
}

function Row({ label, value, accent }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.05)',
    }}>
      <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.45)', fontWeight: 400 }}>{label}</span>
      <span style={{ fontSize: '13px', color: accent ?? 'rgba(255,255,255,0.85)', fontWeight: 500 }}>
        {value ?? '—'}
      </span>
    </div>
  );
}

function BarRow({ label, value, max, suffix, danger = false, warn = false }) {
  return (
    <div style={{ padding: '10px 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
        <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.45)' }}>{label}</span>
        <span style={{ fontSize: '13px', fontWeight: 500, color: danger ? '#ff6b6b' : warn ? '#f5c518' : 'rgba(255,255,255,0.85)' }}>
          {suffix ?? value}
        </span>
      </div>
      <Bar value={value} max={max} danger={danger} warn={warn} />
    </div>
  );
}

export default function Metrics() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError]     = useState('');
  const navigate              = useNavigate();

  useEffect(() => {
    api.getMetrics().then(setMetrics).catch(e => setError(e.message));
  }, []);

  const tier         = metrics?.tier ?? 'free';
  const dayLimit     = DAILY_LIMITS[tier] ?? 10;
  const reqToday     = metrics?.requests_today ?? 0;
  const successRate  = metrics?.tasks?.success_rate ?? 0;
  const totalTasks   = metrics?.tasks?.total ?? 0;
  const doneTasks    = metrics?.tasks?.completed ?? 0;
  const cost         = metrics?.llm_usage?.estimated_cost_usd ?? 0;

  const tierColor =
    tier === 'enterprise' ? '#fff' :
    tier === 'pro'        ? '#f5c518' :
    'rgba(255,255,255,0.4)';

  return (
    <Layout status="Usage Metrics — API Online">
      <div style={{ flex: 1, overflowY: 'auto', padding: '48px 52px' }}>

        {/* Page header */}
        <div style={{ marginBottom: '52px', display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between' }}>
          <div>
            <div style={{
              fontSize: '9px', fontWeight: 700, letterSpacing: '0.2em',
              color: 'rgba(255,255,255,0.28)', textTransform: 'uppercase', marginBottom: '10px',
            }}>
              Meta-Agent
            </div>
            <div style={{ fontFamily: "'Chiqueta', 'Inter', sans-serif", fontSize: 'clamp(2rem, 5vw, 4rem)', fontWeight: 400, letterSpacing: '0.01em', lineHeight: 1 }}>
              Usage Metrics
            </div>
          </div>
          <button
            className="tbtn"
            onClick={() => navigate('/')}
            style={{ alignSelf: 'flex-start', marginTop: '8px' }}
          >
            ← Dashboard
          </button>
        </div>

        {!metrics && !error && (
          <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.3)', letterSpacing: '0.1em' }} className="animate-pulse">
            Loading...
          </div>
        )}

        {error && (
          <div style={{ color: '#ff6b6b', fontSize: '14px' }}>{error}</div>
        )}

        {metrics && (
          <div style={{ maxWidth: '520px', display: 'flex', flexDirection: 'column' }}>

            <Section title="Account">
              <Row label="User ID" value={metrics.user_id} />
              <Row label="Tier" value={tier.toUpperCase()} accent={tierColor} />
            </Section>

            <Section title="Daily Usage">
              <BarRow
                label="Requests Today"
                value={reqToday}
                max={dayLimit}
                suffix={`${reqToday} / ${dayLimit}`}
                danger={reqToday >= dayLimit * 0.9}
                warn={reqToday >= dayLimit * 0.6 && reqToday < dayLimit * 0.9}
              />
            </Section>

            <Section title="Tasks">
              <Row label="Total Projects" value={metrics.projects} />
              <Row label="Total Tasks"    value={totalTasks} />
              <BarRow
                label="Completed"
                value={doneTasks}
                max={totalTasks || 1}
                suffix={`${doneTasks} / ${totalTasks}`}
              />
              <BarRow
                label="Success Rate"
                value={successRate}
                max={100}
                suffix={`${successRate}%`}
                danger={successRate < 50}
                warn={successRate >= 50 && successRate < 80}
              />
            </Section>

            <Section title="LLM Usage">
              <Row label="Total Calls"     value={metrics.llm_usage?.total_calls} />
              <Row label="Tokens Used"     value={metrics.llm_usage?.total_tokens?.toLocaleString()} />
              <Row
                label="Estimated Cost"
                value={`$${cost}`}
                accent={cost > 1 ? '#f5c518' : 'rgba(255,255,255,0.85)'}
              />
            </Section>

          </div>
        )}
      </div>
    </Layout>
  );
}

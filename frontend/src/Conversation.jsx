import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from './Layout';
import ResultsPanel from './ResultsPanel';
import ProgressTracker from './ProgressTracker';
import FileBrowser from './FileBrowser';
import { api, streamConversation } from './api';

// ── Message bubble ─────────────────────────────────────────────────────────────
function Bubble({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div style={{ marginBottom: '28px' }}>
      <div style={{
        fontSize: '9px', fontWeight: 700, letterSpacing: '0.16em',
        textTransform: 'uppercase', marginBottom: '7px',
        color: isUser ? 'rgba(255,255,255,0.35)' : 'rgba(255,255,255,0.55)',
      }}>
        {isUser ? 'You' : 'Agent'}
      </div>
      <div style={{
        fontSize: '14px', lineHeight: '1.7',
        whiteSpace: 'pre-wrap', wordBreak: 'break-word',
        color: isUser ? '#fff' : 'rgba(255,255,255,0.82)',
        paddingLeft: isUser ? 0 : '12px',
        borderLeft: isUser ? 'none' : '2px solid rgba(255,255,255,0.1)',
      }}>
        {msg.content}
      </div>
    </div>
  );
}

// ── Requirements panel ─────────────────────────────────────────────────────────
function RequirementsPanel({ requirements }) {
  const [open, setOpen] = useState(false);
  if (!requirements || Object.keys(requirements).length === 0) return null;
  const entries = Object.entries(requirements).filter(([, v]) => v);
  return (
    <div style={{ flexShrink: 0, borderBottom: '1px solid rgba(255,255,255,0.07)', background: '#0a0a0a' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
          padding: '10px 20px', background: 'none', border: 'none', cursor: 'pointer',
          fontFamily: 'inherit', color: 'rgba(255,255,255,0.4)',
          fontSize: '10px', fontWeight: 600, letterSpacing: '0.12em', textTransform: 'uppercase',
          transition: 'color 0.1s',
        }}
        onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
        onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.4)')}
      >
        <span>Requirements Gathered</span>
        <span style={{ color: 'rgba(255,255,255,0.25)' }}>{entries.length} items</span>
        <span style={{ marginLeft: 'auto' }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && (
        <div style={{ padding: '0 20px 14px', display: 'flex', flexDirection: 'column', gap: '6px' }}>
          {entries.map(([k, v]) => (
            <div key={k} style={{ display: 'flex', gap: '12px', fontSize: '13px' }}>
              <span style={{ color: 'rgba(255,255,255,0.35)', flexShrink: 0, textTransform: 'capitalize' }}>
                {k.replace(/_/g, ' ')}
              </span>
              <span style={{ color: 'rgba(255,255,255,0.8)', wordBreak: 'break-word' }}>
                {typeof v === 'object' ? JSON.stringify(v) : String(v)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Status badge ───────────────────────────────────────────────────────────────
function StatusBadge({ status, isExecuting }) {
  const executing = isExecuting;
  const color =
    status === 'completed' && !executing ? '#fff'    :
    executing                            ? '#fff'    :
    'rgba(255,255,255,0.35)';
  const bg =
    status === 'completed' && !executing ? 'rgba(255,255,255,0.08)' :
    executing                            ? 'rgba(255,255,255,0.05)' :
    'transparent';
  const border =
    status === 'completed' && !executing ? 'rgba(255,255,255,0.3)' :
    executing                            ? 'rgba(255,255,255,0.2)' :
    'rgba(255,255,255,0.1)';
  return (
    <span style={{
      padding: '3px 10px', fontSize: '10px', fontWeight: 600, letterSpacing: '0.1em',
      textTransform: 'uppercase', color, background: bg,
      border: `1px solid ${border}`, borderRadius: '2px',
    }} className={executing ? 'animate-pulse' : ''}>
      {status.replace(/_/g, ' ')}
    </span>
  );
}

// ── Main component ─────────────────────────────────────────────────────────────
export default function Conversation() {
  const { id }                    = useParams();
  const [conv, setConv]           = useState(null);
  const [message, setMessage]     = useState('');
  const [sending, setSending]     = useState(false);
  const [tasks, setTasks]         = useState([]);
  const [streaming, setStreaming] = useState(false);
  const [streamError, setStreamError] = useState(null);
  const [showFiles, setShowFiles] = useState(false);
  const [deleting, setDeleting]   = useState(false);
  const streamGuard               = useRef(false);
  const endRef                    = useRef(null);
  const navigate                  = useNavigate();

  useEffect(() => {
    api.getConversation(id).then(data => {
      setConv(data);
      if (data.status === 'executing') startStream();
    }).catch(() => navigate('/'));
  }, [id]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conv?.messages?.length]);

  const startStream = async () => {
    if (streamGuard.current) return;
    streamGuard.current = true;
    setStreaming(true);
    setStreamError(null);
    try {
      for await (const evt of streamConversation(id)) {
        if (evt.type === 'task_update') {
          setTasks(prev => {
            const idx = prev.findIndex(t => t.task_id === evt.task_id);
            if (idx >= 0) { const next = [...prev]; next[idx] = evt; return next; }
            return [...prev, evt];
          });
        }
        if (evt.type === 'timeout') {
          setStreamError('Execution timed out. The agents may still be running in the background.');
          break;
        }
        if (evt.type === 'done' || (evt.type === 'conversation_status' && evt.status === 'completed')) {
          const updated = await api.getConversation(id);
          setConv(updated); setStreaming(false); streamGuard.current = false; return;
        }
      }
    } catch { /* SSE connection ended */ }
    const updated = await api.getConversation(id).catch(() => null);
    if (updated) setConv(updated);
    setStreaming(false); streamGuard.current = false;
  };

  const send = async () => {
    if (!message.trim() || sending) return;
    setSending(true);
    try {
      const updated = await api.sendMessage(id, message.trim());
      setMessage(''); setConv(updated);
      if (updated.status === 'executing') startStream();
    } catch (err) { console.error(err); }
    finally { setSending(false); }
  };

  const deleteConv = async () => {
    if (!window.confirm('Delete this session? This cannot be undone.')) return;
    setDeleting(true);
    try { await api.deleteConversation(id); navigate('/'); }
    catch (err) { alert(err.message); setDeleting(false); }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const isGathering = conv?.status === 'gathering_requirements';
  const isReady     = conv?.status === 'ready_to_execute';
  const isExecuting = conv?.status === 'executing' || streaming;
  const isCompleted = conv?.status === 'completed' && !streaming;
  const isRefining  = conv?.status === 'refining';
  const isFailed    = conv?.status === 'failed';

  const getResult = () => {
    if (!conv?.messages) return null;
    for (let i = conv.messages.length - 1; i >= 0; i--) {
      if (conv.messages[i].result) return conv.messages[i].result;
    }
    return null;
  };
  const result = getResult();

  const statusText = conv
    ? `Session ${id} — ${conv.mode} — ${conv.status.replace(/_/g, ' ')}`
    : `Session ${id} — Loading`;

  const inputPlaceholder =
    isGathering ? 'Answer the question above...' :
    isReady     ? 'Type "execute" to run, or describe changes...' :
    isCompleted ? 'Ask to refine or modify the output...' :
    isRefining  ? 'Refinement in progress...' :
                  'Type a message...';

  if (!conv) {
    return (
      <Layout status="Loading...">
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <span style={{ fontSize: '13px', color: 'rgba(255,255,255,0.35)', letterSpacing: '0.12em' }}
                className="animate-pulse">
            LOADING
          </span>
        </div>
      </Layout>
    );
  }

  return (
    <Layout status={statusText}>
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

        {/* Header */}
        <div style={{
          flexShrink: 0, borderBottom: '1px solid rgba(255,255,255,0.07)',
          padding: '10px 20px', display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap',
        }}>
          <button
            className="tbtn"
            onClick={() => navigate('/')}
            style={{ padding: '5px 12px' }}
          >
            ← Back
          </button>
          <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)', fontWeight: 500 }}>
            Session {id}
          </span>
          <span style={{
            padding: '3px 10px', fontSize: '10px', fontWeight: 600, letterSpacing: '0.1em',
            textTransform: 'uppercase', color: 'rgba(255,255,255,0.5)',
            border: '1px solid rgba(255,255,255,0.1)', borderRadius: '2px',
          }}>
            {conv.mode}
          </span>
          <StatusBadge status={conv.status} isExecuting={isExecuting} />

          <div style={{ marginLeft: 'auto', display: 'flex', gap: '8px' }}>
            {isCompleted && result && (
              <button className="tbtn" onClick={() => setShowFiles(true)}>Files</button>
            )}
            <button
              className="tbtn"
              onClick={deleteConv}
              disabled={deleting || isExecuting}
              style={deleting ? {} : { borderColor: 'rgba(255,100,100,0.25)', color: 'rgba(255,120,120,0.7)' }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = 'rgba(255,100,100,0.6)'; e.currentTarget.style.color = '#ff6b6b'; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(255,100,100,0.25)'; e.currentTarget.style.color = 'rgba(255,120,120,0.7)'; }}
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>

        {/* Body */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>

          {conv.mode === 'hardcore' && (isGathering || isReady) && conv.gathered_requirements && (
            <RequirementsPanel requirements={conv.gathered_requirements} />
          )}

          {isReady && conv.final_prompt && (
            <div style={{
              flexShrink: 0, borderBottom: '1px solid rgba(255,255,255,0.07)',
              padding: '10px 20px', background: '#0a0a0a',
              fontSize: '12px', color: 'rgba(255,255,255,0.5)',
            }}>
              <strong style={{ color: '#fff' }}>Final spec ready</strong>
              <span style={{ marginLeft: '8px' }}>— type "execute" to build or ask for changes</span>
            </div>
          )}

          {(isExecuting || tasks.length > 0) && (
            <ProgressTracker tasks={tasks} />
          )}

          {isCompleted && result && (
            <ResultsPanel result={result} onShowFiles={() => setShowFiles(true)} />
          )}

          {(!isCompleted || !result) && (
            <div style={{ flex: 1, overflowY: 'auto', padding: '32px 28px' }}>
              {conv.messages.map((msg, i) => <Bubble key={i} msg={msg} />)}
              {isExecuting && tasks.length === 0 && (
                <div style={{ fontSize: '13px', color: 'rgba(255,255,255,0.3)', letterSpacing: '0.05em' }}
                     className="animate-pulse">
                  Initializing agent pipeline...
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}

          {isCompleted && result && conv.mode === 'hardcore' && (
            <div style={{
              flexShrink: 0, borderTop: '1px solid rgba(255,255,255,0.07)',
              padding: '12px 28px', maxHeight: '130px', overflowY: 'auto',
            }}>
              {conv.messages.slice(-3).map((msg, i) => <Bubble key={i} msg={msg} />)}
            </div>
          )}
        </div>

        {/* Input area */}
        {(isGathering || isReady || isCompleted || isRefining || isFailed) && (
          <div style={{
            flexShrink: 0, borderTop: '1px solid rgba(255,255,255,0.07)',
            padding: '16px 20px',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
              <span style={{
                fontSize: '10px', fontWeight: 600, letterSpacing: '0.12em',
                textTransform: 'uppercase', color: 'rgba(255,255,255,0.25)',
                marginTop: '10px', flexShrink: 0,
              }}>
                {isReady ? 'Reply' : isCompleted ? 'Refine' : 'Answer'}
              </span>
              <textarea
                style={{
                  flex: 1, background: 'transparent', border: 'none', outline: 'none',
                  color: '#fff', fontFamily: 'inherit', fontSize: '14px', lineHeight: '1.6',
                  resize: 'none', overflowY: 'auto', padding: '8px 0',
                }}
                placeholder={inputPlaceholder}
                rows={2}
                value={message}
                onChange={e => setMessage(e.target.value)}
                onKeyDown={handleKey}
                disabled={sending || isRefining}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '8px' }}>
              <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.25)' }}>
                {isReady     && 'Requirements gathered — type "execute" to build'}
                {isRefining  && 'Refining...'}
              </span>
              <button
                className="tbtn"
                onClick={send}
                disabled={sending || !message.trim() || isRefining}
                style={{ padding: '6px 20px' }}
              >
                {sending ? 'Sending...' : 'Send'}
              </button>
            </div>
          </div>
        )}

        {/* Error / timeout banner */}
        {(streamError || isFailed) && (
          <div style={{
            flexShrink: 0, borderTop: '1px solid rgba(255,100,100,0.2)',
            padding: '10px 20px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            fontSize: '12px', color: 'rgba(255,150,150,0.9)', background: 'rgba(255,50,50,0.06)',
          }}>
            <span>{streamError || 'This conversation encountered an error. You can reset it or start a new one.'}</span>
            <button
              className="tbtn"
              style={{ flexShrink: 0, borderColor: 'rgba(255,100,100,0.3)', color: 'rgba(255,150,150,0.9)' }}
              onClick={async () => {
                setStreamError(null);
                const updated = await api.getConversation(id).catch(() => null);
                if (updated) setConv(updated);
                if (updated?.status === 'executing') startStream();
              }}
            >
              Refresh
            </button>
          </div>
        )}

        {/* Executing notice */}
        {isExecuting && (
          <div style={{
            flexShrink: 0, borderTop: '1px solid rgba(255,255,255,0.07)',
            padding: '10px 20px', fontSize: '11px', fontWeight: 500,
            color: 'rgba(255,255,255,0.35)', letterSpacing: '0.06em',
          }} className="animate-pulse">
            Agents running — this may take 30–60 seconds...
          </div>
        )}
      </div>

      {showFiles && conv.project_id && (
        <FileBrowser
          projectId={conv.project_id}
          projectName={`session_${id}`}
          onClose={() => setShowFiles(false)}
        />
      )}
    </Layout>
  );
}

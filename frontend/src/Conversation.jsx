import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import Layout from './Layout';
import ResultsPanel from './ResultsPanel';
import ProgressTracker from './ProgressTracker';
import { api, streamConversation } from './api';

// ── Message bubble ────────────────────────────────────────────────────────────
function Bubble({ msg }) {
  const isUser = msg.role === 'user';
  return (
    <div className={`flex gap-3 ${isUser ? '' : 'pl-2'}`}>
      <span className={`shrink-0 text-base ${isUser ? 'text-g-dim' : 'text-g-bright'}`}>
        {isUser ? 'you:' : 'agent:'}
      </span>
      <span className={`text-base whitespace-pre-wrap break-words ${isUser ? 'text-g-bright' : 'text-g-med'}`}>
        {msg.content}
      </span>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function Conversation() {
  const { id }                    = useParams();
  const [conv, setConv]           = useState(null);
  const [message, setMessage]     = useState('');
  const [sending, setSending]     = useState(false);
  const [tasks, setTasks]         = useState([]);
  const [streaming, setStreaming] = useState(false);
  const streamGuard               = useRef(false);
  const endRef                    = useRef(null);
  const navigate                  = useNavigate();

  // ── Load conversation ─────────────────────────────────────────────────────
  useEffect(() => {
    api.getConversation(id).then(data => {
      setConv(data);
      // If already executing when we land here, start SSE immediately
      if (data.status === 'executing') startStream();
    }).catch(() => navigate('/'));
  }, [id]);

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conv?.messages?.length]);

  // ── SSE stream ────────────────────────────────────────────────────────────
  const startStream = async () => {
    if (streamGuard.current) return;
    streamGuard.current = true;
    setStreaming(true);
    try {
      for await (const evt of streamConversation(id)) {
        if (evt.type === 'task_update') {
          setTasks(prev => {
            const idx = prev.findIndex(t => t.task_id === evt.task_id);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = evt;
              return next;
            }
            return [...prev, evt];
          });
        }
        if (evt.type === 'done' || (evt.type === 'conversation_status' && evt.status === 'completed')) {
          const updated = await api.getConversation(id);
          setConv(updated);
          setStreaming(false);
          streamGuard.current = false;
          return;
        }
      }
    } catch { /* SSE ended */ }
    // Fallback: refresh conversation
    const updated = await api.getConversation(id).catch(() => null);
    if (updated) setConv(updated);
    setStreaming(false);
    streamGuard.current = false;
  };

  // ── Send message ──────────────────────────────────────────────────────────
  const send = async () => {
    if (!message.trim() || sending) return;
    setSending(true);
    try {
      const updated = await api.sendMessage(id, message.trim());
      setMessage('');
      setConv(updated);
      if (updated.status === 'executing') startStream();
    } catch (err) {
      console.error(err);
    } finally {
      setSending(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  // ── Derive display state ──────────────────────────────────────────────────
  const isGathering  = conv?.status === 'gathering_requirements';
  const isReady      = conv?.status === 'ready_to_execute';
  const isExecuting  = conv?.status === 'executing' || streaming;
  const isCompleted  = conv?.status === 'completed' && !streaming;
  const isRefining   = conv?.status === 'refining';

  const getResult = () => {
    if (!conv?.messages) return null;
    for (let i = conv.messages.length - 1; i >= 0; i--) {
      if (conv.messages[i].result) return conv.messages[i].result;
    }
    return null;
  };
  const result = getResult();

  const statusText = conv
    ? `session: ${id} | ${conv.mode} | ${conv.status.replace(/_/g, ' ')}`
    : `session: ${id} | loading...`;

  // ── Render ────────────────────────────────────────────────────────────────
  if (!conv) {
    return (
      <Layout status="loading...">
        <div className="flex-1 flex items-center justify-center">
          <span className="text-g-dim animate-pulse cursor text-xl">LOADING</span>
        </div>
      </Layout>
    );
  }

  return (
    <Layout status={statusText}>
      <div className="flex-1 flex flex-col overflow-hidden">

        {/* Header bar */}
        <div className="shrink-0 border-b border-g-border px-4 py-2 flex items-center gap-4 flex-wrap">
          <button className="tbtn" onClick={() => navigate('/')}>← back</button>
          <span className="text-g-dim text-base">
            session_{id}
          </span>
          <span className="border border-g-border px-3 py-0.5 text-sm">
            {conv.mode.toUpperCase()}
          </span>
          <span className={`border px-3 py-0.5 text-sm ${
            isCompleted  ? 'border-g-bright text-g-bright'   :
            isExecuting  ? 'border-yellow-600 text-yellow-400 animate-pulse' :
            isGathering  ? 'border-g-border text-g-dim'      :
                           'border-g-border text-g-dim'
          }`}>
            {conv.status.replace(/_/g, ' ').toUpperCase()}
          </span>
        </div>

        {/* Body */}
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* Progress tracker (visible while executing) */}
          {(isExecuting || tasks.length > 0) && (
            <ProgressTracker tasks={tasks} />
          )}

          {/* Results panel (completed and has output) */}
          {isCompleted && result && (
            <ResultsPanel result={result} />
          )}

          {/* Chat messages (always show for HARDCORE; show while normal is pending/gathering) */}
          {(!isCompleted || !result) && (
            <div className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
              {conv.messages.map((msg, i) => (
                <Bubble key={i} msg={msg} />
              ))}
              {isExecuting && tasks.length === 0 && (
                <div className="text-g-dim text-base animate-pulse">
                  {'>'} initializing agent pipeline...
                </div>
              )}
              <div ref={endRef} />
            </div>
          )}

          {/* Show messages alongside results for HARDCORE completed */}
          {isCompleted && result && conv.mode === 'hardcore' && (
            <div className="shrink-0 border-t border-g-border px-4 py-2 max-h-32 overflow-y-auto">
              {conv.messages.slice(-3).map((msg, i) => (
                <Bubble key={i} msg={msg} />
              ))}
            </div>
          )}
        </div>

        {/* Input area */}
        {(isGathering || isReady || isCompleted || isRefining) && (
          <div className="shrink-0 border-t border-g-border px-4 py-3">
            <div className="flex items-start gap-2">
              <span className="text-g-dim text-lg mt-1 whitespace-nowrap shrink-0">
                meta@agent:~$
              </span>
              <textarea
                className="flex-1 bg-transparent border-none outline-none text-g-bright font-term text-lg resize-none overflow-y-auto"
                placeholder={
                  isGathering ? 'Answer the question above...' :
                  isReady     ? 'Type "execute" to run, or describe changes...' :
                  isCompleted ? 'Ask to refine or modify...' :
                                'Type a message...'
                }
                rows={2}
                value={message}
                onChange={e => setMessage(e.target.value)}
                onKeyDown={handleKey}
                disabled={sending}
              />
            </div>
            <div className="flex items-center justify-between mt-2">
              {isReady && (
                <span className="text-g-dim text-sm">
                  {'>'} requirements gathered — type "execute" to build
                </span>
              )}
              <button
                className="tbtn ml-auto"
                onClick={send}
                disabled={sending || !message.trim()}
              >
                {sending ? 'SENDING...' : 'SEND'}
              </button>
            </div>
          </div>
        )}

        {/* Executing notice */}
        {isExecuting && (
          <div className="shrink-0 border-t border-g-border px-4 py-2 text-g-dim text-base animate-pulse">
            {'>'} agents running — this may take 30–60 seconds...
          </div>
        )}
      </div>
    </Layout>
  );
}

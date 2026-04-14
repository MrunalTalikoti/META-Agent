export default function ProgressTracker({ tasks }) {
  const icon = (status) => {
    switch (status) {
      case 'completed':   return <span className="text-g-bright">✓</span>;
      case 'failed':      return <span className="text-red-400">✗</span>;
      case 'in_progress': return <span className="text-g-bright animate-blink">▶</span>;
      default:            return <span className="text-g-dim">○</span>;
    }
  };

  const label = (status) => {
    switch (status) {
      case 'in_progress': return <span className="text-g-bright animate-pulse">running</span>;
      case 'completed':   return <span className="text-g-bright">done</span>;
      case 'failed':      return <span className="text-red-400">failed</span>;
      default:            return <span className="text-g-dim">pending</span>;
    }
  };

  return (
    <div className="border-b border-g-border px-4 py-3 shrink-0">
      <div className="text-g-dim text-base mb-2">{'>'} AGENT PIPELINE</div>
      <div className="space-y-1">
        {tasks.map((t, i) => (
          <div key={t.task_id ?? i} className="flex items-center gap-3 text-base font-term">
            <span className="w-4 text-center shrink-0">{icon(t.status)}</span>
            <span
              className={
                t.status === 'failed'      ? 'text-red-400' :
                t.status === 'completed'   ? 'text-g-bright' :
                t.status === 'in_progress' ? 'text-g-bright' :
                'text-g-dim'
              }
            >
              {(t.agent || t.title || 'task').replace(/_/g, ' ')}
            </span>
            <span className="ml-auto shrink-0 text-sm">
              {label(t.status)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

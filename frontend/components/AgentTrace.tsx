'use client'
import { useState } from 'react'
import { ChevronDown, ChevronRight, CheckCircle2, Circle, Loader2, AlertCircle, Cpu, Search, FileCode, TestTube, Server, Globe } from 'lucide-react'
import { TraceEvent } from '@/lib/store'

const AGENT_ICONS: Record<string, React.ReactNode> = {
  coder: <FileCode size={12} />,
  researcher: <Search size={12} />,
  web_surfer: <Globe size={12} />,
  tester: <TestTube size={12} />,
  devops: <Server size={12} />,
  analyst: <Cpu size={12} />,
  file_manager: <FileCode size={12} />,
}

const AGENT_COLORS: Record<string, string> = {
  coder: '#D97757',
  researcher: '#1D9E75',
  web_surfer: '#185FA5',
  tester: '#BA7517',
  devops: '#D85A30',
  analyst: '#E8A185',
  file_manager: '#BE5D3D',
}

interface AgentTraceProps {
  events: TraceEvent[]
}

export default function AgentTrace({ events }: AgentTraceProps) {
  const [open, setOpen] = useState(true)
  if (!events.length) return null

  const planEvent = events.find(e => e.type === 'plan')
  const agentEvents = events.filter(e => ['agent_start', 'agent_done', 'validation', 'retry'].includes(e.type))
  const statusEvents = events.filter(e => e.type === 'status')
  const lastStatus = statusEvents[statusEvents.length - 1]

  // Group by task_id
  const tasks: Record<string, TraceEvent[]> = {}
  for (const e of agentEvents) {
    const tid = e.task_id || 'main'
    if (!tasks[tid]) tasks[tid] = []
    tasks[tid].push(e)
  }

  return (
    <div style={{
      border: '0.5px solid var(--border)', borderRadius: 8,
      background: 'var(--bg-secondary)', marginBottom: 10, overflow: 'hidden'
    }}>
      {/* Header */}
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 8,
          padding: '8px 12px', background: 'none', border: 'none',
          color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 12
        }}
      >
        <Cpu size={13} style={{ color: 'var(--brand)' }} />
        <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>Agent execution trace</span>
        {lastStatus && (
          <span style={{ marginLeft: 8, color: 'var(--text-muted)', fontSize: 11 }}>
            {lastStatus.message}
          </span>
        )}
        <span style={{ marginLeft: 'auto' }}>{open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}</span>
      </button>

      {open && (
        <div style={{ padding: '6px 12px 10px', borderTop: '0.5px solid var(--border)' }}>
          {/* Plan summary */}
          {planEvent?.subtasks && (
            <div style={{ marginBottom: 10 }}>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>
                Plan: {planEvent.subtasks.length} subtask{planEvent.subtasks.length > 1 ? 's' : ''}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
                {planEvent.subtasks.map((t, i) => (
                  <span key={t.id} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 10,
                      padding: '2px 8px', borderRadius: 99, fontWeight: 500,
                      background: `${AGENT_COLORS[t.agent_type] || '#D97757'}22`,
                      color: AGENT_COLORS[t.agent_type] || '#D97757',
                      border: `0.5px solid ${AGENT_COLORS[t.agent_type] || '#D97757'}44`
                    }}>
                      {AGENT_ICONS[t.agent_type]} {t.agent_type}
                    </span>
                    {t.depends_on && t.depends_on.length > 0 && (
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                        ← {t.depends_on.join(',')}
                      </span>
                    )}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Task steps */}
          {Object.entries(tasks).map(([tid, tevents]) => {
            const startEvt = tevents.find(e => e.type === 'agent_start')
            const doneEvt = tevents.find(e => e.type === 'agent_done')
            const validations = tevents.filter(e => e.type === 'validation')
            const lastValidation = validations[validations.length - 1]
            const isRunning = startEvt && !doneEvt
            const agentType = startEvt?.agent_type || 'coder'

            return (
              <div key={tid} style={{ marginBottom: 8, display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                {/* Icon */}
                <div style={{
                  width: 22, height: 22, borderRadius: '50%', flexShrink: 0, marginTop: 1,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: doneEvt
                    ? (lastValidation?.passed === false ? 'rgba(216,90,48,0.2)' : 'rgba(29,158,117,0.2)')
                    : isRunning ? 'rgba(217,119,87,0.2)' : 'rgba(255,255,255,0.05)',
                  color: doneEvt
                    ? (lastValidation?.passed === false ? 'var(--red)' : 'var(--green)')
                    : isRunning ? 'var(--brand)' : 'var(--text-muted)'
                }}>
                  {isRunning
                    ? <Loader2 size={12} style={{ animation: 'spin 0.8s linear infinite' }} />
                    : doneEvt
                      ? (lastValidation?.passed === false ? <AlertCircle size={12} /> : <CheckCircle2 size={12} />)
                      : <Circle size={12} />
                  }
                </div>

                {/* Content */}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-primary)' }}>
                      {agentType.replace('_', ' ')} agent
                    </span>
                    {validations.map((v, i) => (
                      <span key={i} style={{
                        fontSize: 10, padding: '1px 6px', borderRadius: 99,
                        background: v.passed ? 'rgba(29,158,117,0.15)' : 'rgba(216,90,48,0.15)',
                        color: v.passed ? 'var(--green)' : 'var(--red)'
                      }}>
                        {v.passed ? `✓ ${v.score}` : `✗ attempt ${v.attempt}`}
                      </span>
                    ))}
                  </div>
                  {startEvt?.description && (
                    <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2, lineHeight: 1.4 }}>
                      {startEvt.description}
                    </div>
                  )}
                  {lastValidation && !lastValidation.passed && lastValidation.feedback && (
                    <div style={{
                      fontSize: 11, color: 'var(--amber)', marginTop: 4, padding: '4px 8px',
                      background: 'rgba(186,117,23,0.1)', borderRadius: 4, borderLeft: '2px solid var(--amber)'
                    }}>
                      Feedback: {lastValidation.feedback}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

'use client'
import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Code2, Paperclip, Square, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useStore, Message, TraceEvent, CodeSession } from '@/lib/store'
import { CodeSocket, api } from '@/lib/api'
import AgentTrace from './AgentTrace'
import ModelPicker from '@/components/ModelPicker'
import MicButton from '@/components/MicButton'
import CodeBlock from '@/components/CodeBlock'

function MessageBubble({ msg }: { msg: Message }) {
  const traceEvents: TraceEvent[] = msg.meta?.trace || []

  if (msg.role === 'user') {
    return (
      <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'flex-end' }}>
        <div style={{ maxWidth: '85%' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 5, textAlign: 'right' }}>You</div>
          <div style={{
            background: 'rgba(217,119,87,0.12)', border: '0.5px solid rgba(217,119,87,0.22)',
            borderRadius: 10, padding: '10px 14px', fontSize: 14,
            color: 'var(--text-primary)', lineHeight: 1.6, whiteSpace: 'pre-wrap'
          }}>
            {msg.content}
          </div>
        </div>
      </div>
    )
  }

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{
          width: 20, height: 20, background: 'var(--brand-dark)', borderRadius: 6,
          display: 'flex', alignItems: 'center', justifyContent: 'center'
        }}>
          <Code2 size={12} color="white" />
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>CrewDev Code Agent</span>
      </div>

      {traceEvents.length > 0 && <AgentTrace events={traceEvents} />}

      <div className="prose-dark">
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={{ pre: ({ children }: any) => <>{children}</>, code: CodeBlock }}>{msg.content || ''}</ReactMarkdown>
        {msg.streaming && (
          <span style={{
            display: 'inline-block', width: 8, height: 14, background: 'var(--brand)',
            borderRadius: 1, marginLeft: 2, animation: 'pulse 1s ease-in-out infinite',
            verticalAlign: 'text-bottom'
          }} />
        )}
      </div>
    </div>
  )
}

interface CodePanelProps {
  session: CodeSession
}

export default function CodePanel({ session }: CodePanelProps) {
  const {
    messages, setMessages, addMessage, appendTraceEvent, clearTrace,
    isStreaming, setStreaming, setUsage, setErrorMessage, updateCodeSession, setFileTree
  } = useStore()
  const [input, setInput] = useState('')
  const [activeSkills, setActiveSkills] = useState<string[]>([])
  const [status, setStatus] = useState<string | null>(null)
  const [attachments, setAttachments] = useState<{ name: string; kind: string; text?: string; data_url?: string }[]>([])
  const bottomRef = useRef<HTMLDivElement>(null)
  const socketRef = useRef<CodeSocket | null>(null)
  const activeTraceRef = useRef<TraceEvent[]>([])
  const streamBufRef = useRef<string>('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    let cancelled = false
    setStreaming(false)
    setUsage(null)
    setErrorMessage(null)
    clearTrace()
    activeTraceRef.current = []
    streamBufRef.current = ''
    setStatus(null)

    api.code.messages(session.id).then(msgs => {
      if (cancelled) return
      setMessages(msgs.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        meta: m.meta,
        created_at: m.created_at,
      })))
    }).catch((error) => {
      if (!cancelled) {
        setMessages([])
        setErrorMessage(`Unable to load Code history: ${error.message}`)
      }
    })

    api.projects.files(session.project_id).then(r => setFileTree(r.tree)).catch(() => {})

    return () => { cancelled = true }
  }, [session.id, session.project_id, setMessages, setStreaming, setUsage, setErrorMessage, clearTrace, setFileTree])

  useEffect(() => {
    const sock = new CodeSocket(session.id)
    sock.connect()
    socketRef.current = sock

    const off = sock.on((event) => {
      if (event.type === 'token') {
        streamBufRef.current += event.text || ''
        const buf = streamBufRef.current
        setMessages(prev => {
          const safePrev = Array.isArray(prev) ? prev : []
          const hasStreaming = safePrev.some(m => m.streaming)
          if (hasStreaming) return safePrev.map(m => m.streaming ? { ...m, content: buf } : m)
          return [...safePrev, { id: 'streaming-code', role: 'assistant', content: buf, streaming: true }]
        })
        return
      }

      if (event.type === 'final') {
        const trace = [...activeTraceRef.current]
        const finalText = event.content || streamBufRef.current || 'Done.'
        activeTraceRef.current = []
        streamBufRef.current = ''
        setMessages(prev => {
          const safePrev = Array.isArray(prev) ? prev : []
          const withoutStreaming = safePrev.filter(m => !m.streaming)
          return [...withoutStreaming, {
            id: event.id || Date.now().toString(),
            role: 'assistant',
            content: finalText,
            meta: { trace },
          }]
        })
        setStreaming(false)
        setStatus(null)
        api.projects.files(session.project_id).then(r => setFileTree(r.tree)).catch(() => {})
        return
      }

      if (event.type === 'usage') {
        setUsage({
          total_tokens: event.total_tokens || 0,
          cost_usd: event.cost_usd || 0,
          calls: event.calls || 0,
        })
        return
      }

      if (event.type === 'error') {
        const message = event.message || 'Unknown Code agent error.'
        setMessages(prev => {
          const safePrev = Array.isArray(prev) ? prev : []
          return safePrev.filter(m => !m.streaming).concat({
            id: Date.now().toString(),
            role: 'assistant',
            content: `Error: ${message}`,
          })
        })
        setErrorMessage(message)
        setStreaming(false)
        setStatus(null)
        return
      }

      if (event.type === 'skills_activated') {
        setActiveSkills(event.names || [])
        return
      }

      activeTraceRef.current.push(event)
      appendTraceEvent(event)
      const statusMsg = event.message || event.description || `${event.agent_type || 'Agent'} ${event.type}`
      setStatus(statusMsg)

      if (!streamBufRef.current) {
        setMessages(prev => {
          const safePrev = Array.isArray(prev) ? prev : []
          const hasStreaming = safePrev.some(m => m.streaming)
          if (hasStreaming) return safePrev.map(m => m.streaming ? { ...m, content: statusMsg } : m)
          return [...safePrev, { id: 'streaming-code', role: 'assistant', content: statusMsg, streaming: true }]
        })
      }
    })

    return () => {
      off()
      sock.disconnect()
      if (socketRef.current === sock) socketRef.current = null
    }
  }, [session.id, session.project_id, setMessages, appendTraceEvent, setStreaming, setUsage, setErrorMessage, setFileTree])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function send() {
    const text = input.trim()
    if (!text && attachments.length === 0) return
    if (isStreaming) return
    setInput('')
    setActiveSkills([])
    clearTrace()
    setErrorMessage(null)
    activeTraceRef.current = []
    streamBufRef.current = ''
    addMessage({ id: `user-${Date.now()}`, role: 'user', content: text })
    setStreaming(true)
    setStatus('Code agent starting…')
    socketRef.current?.send(text, attachments)
    setAttachments([])
    if (textareaRef.current) textareaRef.current.style.height = '44px'
  }

  function stop() {
    socketRef.current?.disconnect()
    setStreaming(false)
    setStatus(null)
  }

  function onKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  function onInput(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    const ta = textareaRef.current
    if (ta) {
      ta.style.height = '44px'
      ta.style.height = Math.min(ta.scrollHeight, 180) + 'px'
    }
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
      <div style={{
        height: 46, display: 'flex', alignItems: 'center', padding: '0 20px',
        borderBottom: '0.5px solid var(--border)', gap: 10, flexShrink: 0,
      }}>
        <span style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
          <Code2 size={14} style={{ color: 'var(--brand)' }} /> {session.title || 'Code'}
        </span>
        <select
          value={session.engine || 'crewai'}
          onChange={async (e) => {
            const updated = await api.code.update(session.id, { engine: e.target.value })
            updateCodeSession(session.id, updated)
          }}
          style={{ fontSize: 11, padding: '3px 8px', borderRadius: 99, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '0.5px solid var(--border)', cursor: 'pointer' }}
        >
          <option value="crewai">CrewAI</option>
          <option value="deepagents">DeepAgents</option>
        </select>
        <ModelPicker
          providerId={session.model_provider_id ?? null}
          model={session.model ?? null}
          onChange={async (providerId, model) => {
            const updated = await api.code.update(session.id, { model_provider_id: providerId, model })
            updateCodeSession(session.id, updated)
          }}
        />
        {activeSkills.length > 0 && <span style={{ fontSize: 11, color: 'var(--brand-light)' }}>✨ {activeSkills.join(', ')}</span>}
        {status && <span style={{ fontSize: 11, color: 'var(--brand-light)' }}>{status}</span>}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: '18%', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 30, marginBottom: 12 }}>⌘</div>
            <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>
              What should the Code agent build?
            </div>
            <div style={{ fontSize: 13, maxWidth: 470, margin: '0 auto', lineHeight: 1.6 }}>
              This is a separate Claude Code-style workspace. The agent can inspect files, write code, run safe commands, and validate changes without using Cowork.
            </div>
          </div>
        )}
        <div style={{ maxWidth: 820, margin: '0 auto' }}>
          {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
          <div ref={bottomRef} />
        </div>
      </div>

      <div style={{ padding: '12px 20px 16px', borderTop: '0.5px solid var(--border)', background: 'var(--bg-primary)' }}>
        <div style={{ maxWidth: 820, margin: '0 auto' }}>
          <input ref={fileRef} type="file" multiple style={{ display: 'none' }}
            onChange={async (e) => {
              const fs = e.target.files
              if (!fs?.length) return
              try { const a = await api.attachments.upload(fs); setAttachments(prev => [...prev, ...a]) } catch {}
              if (fileRef.current) fileRef.current.value = ''
            }} />
          {attachments.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
              {attachments.map((a, i) => (
                <span key={i} style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '2px 8px', borderRadius: 99, background: 'var(--bg-tertiary)', border: '0.5px solid var(--border)', color: 'var(--text-secondary)' }}>
                  📎 {a.name}
                  <X size={11} style={{ cursor: 'pointer' }} onClick={() => setAttachments(prev => prev.filter((_, j) => j !== i))} />
                </span>
              ))}
            </div>
          )}
          <div style={{
            display: 'flex', gap: 10, alignItems: 'flex-end',
            border: '0.5px solid var(--border-strong)', borderRadius: 12,
            background: 'var(--bg-secondary)', padding: '8px 12px'
          }}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={onInput}
              onKeyDown={onKeyDown}
              placeholder="Ask the Code agent to create files, fix bugs, run checks…"
              disabled={isStreaming}
              style={{
                flex: 1, border: 'none', outline: 'none', resize: 'none',
                background: 'transparent', fontSize: 14, lineHeight: 1.6,
                color: 'var(--text-primary)', height: 44, maxHeight: 180,
                fontFamily: 'inherit'
              }}
            />
            <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end', paddingBottom: 2 }}>
              <button title="Attach file" onClick={() => fileRef.current?.click()} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}>
                <Paperclip size={16} />
              </button>
              <MicButton onText={(t) => setInput(prev => (prev ? prev + ' ' : '') + t)} disabled={isStreaming} />
              <button
                onClick={isStreaming ? stop : send}
                disabled={!isStreaming && !input.trim() && attachments.length === 0}
                style={{
                  width: 32, height: 32, borderRadius: 8, border: 'none',
                  cursor: !isStreaming && !input.trim() && attachments.length === 0 ? 'default' : 'pointer',
                  background: !isStreaming && !input.trim() && attachments.length === 0 ? 'var(--bg-hover)' : 'var(--brand-dark)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                {isStreaming ? <Square size={13} color="white" /> : <ArrowUp size={15} color={input.trim() || attachments.length > 0 ? 'white' : 'var(--text-muted)'} />}
              </button>
            </div>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6, textAlign: 'center' }}>
            Separate Code pipeline · files and commands run only inside this Code workspace
          </div>
        </div>
      </div>
    </div>
  )
}

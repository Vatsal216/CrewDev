'use client'
import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Paperclip, Volume2, VolumeX, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useStore, Message, TraceEvent } from '@/lib/store'
import { ChatSocket, api } from '@/lib/api'
import AgentTrace from './AgentTrace'
import MicButton from '@/components/MicButton'
import { BrowserTTS } from '@/lib/voice'
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
          <span style={{ fontSize: 9, color: 'white', fontWeight: 600 }}>C</span>
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>CrewDev Project Agent</span>
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

interface ChatPanelProps {
  projectId: string
  sessionId: string
}

export default function ChatPanel({ projectId, sessionId }: ChatPanelProps) {
  const {
    messages, setMessages, addMessage, appendTraceEvent, clearTrace,
    isStreaming, setStreaming, setUsage, setErrorMessage
  } = useStore()
  const [input, setInput] = useState('')
  const [activeSkills, setActiveSkills] = useState<string[]>([])
  const [attachments, setAttachments] = useState<{ name: string; kind: string; text?: string; data_url?: string }[]>([])
  const [readAloud, setReadAloud] = useState(false)
  const readAloudRef = useRef(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const socketRef = useRef<ChatSocket | null>(null)
  const activeTraceRef = useRef<TraceEvent[]>([])
  const streamBufRef = useRef<string>('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const ttsRef = useRef(new BrowserTTS())

  // Load project chat history.
  useEffect(() => {
    let cancelled = false
    setStreaming(false)
    setUsage(null)
    setErrorMessage(null)
    clearTrace()
    activeTraceRef.current = []
    streamBufRef.current = ''

    api.sessions.messages(sessionId).then(msgs => {
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
        setErrorMessage(`Unable to load project chat history: ${error.message}`)
      }
    })

    return () => { cancelled = true }
  }, [sessionId, setMessages, setStreaming, setUsage, setErrorMessage, clearTrace])

  // Project WebSocket.
  useEffect(() => {
    const sock = new ChatSocket(projectId, sessionId)
    sock.connect()
    socketRef.current = sock

    const off = sock.on((event) => {
      if (event.type === 'token') {
        streamBufRef.current += event.text || ''
        const buf = streamBufRef.current
        setMessages(prev => {
          const safePrev = Array.isArray(prev) ? prev : []
          const hasStreaming = safePrev.some(m => m.streaming)
          if (hasStreaming) {
            return safePrev.map(m => m.streaming ? { ...m, content: buf } : m)
          }
          return [...safePrev, { id: 'streaming-project', role: 'assistant', content: buf, streaming: true }]
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
        if (readAloudRef.current) ttsRef.current.speak(finalText)
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
        const message = event.message || 'Unknown project chat error.'
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
        return
      }

      if (event.type === 'skills_activated') {
        setActiveSkills(event.names || [])
        return
      }

      // Trace/status events.
      activeTraceRef.current.push(event)
      appendTraceEvent(event)

      if (!streamBufRef.current) {
        const statusMsg = event.message || event.description || `${event.agent_type || 'Agent'} ${event.type}`
        setMessages(prev => {
          const safePrev = Array.isArray(prev) ? prev : []
          const hasStreaming = safePrev.some(m => m.streaming)
          if (hasStreaming) {
            return safePrev.map(m => m.streaming ? { ...m, content: statusMsg } : m)
          }
          return [...safePrev, {
            id: 'streaming-project',
            role: 'assistant',
            content: statusMsg,
            streaming: true,
          }]
        })
      }
    })

    return () => {
      off()
      sock.disconnect()
      if (socketRef.current === sock) socketRef.current = null
      ttsRef.current.cancel()
    }
  }, [projectId, sessionId, setMessages, appendTraceEvent, setStreaming, setUsage, setErrorMessage])

  // Auto scroll.
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
    socketRef.current?.send(text, attachments)
    setAttachments([])
    if (textareaRef.current) textareaRef.current.style.height = '44px'
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
      ta.style.height = Math.min(ta.scrollHeight, 160) + 'px'
    }
  }

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
      <div style={{
        height: 40, display: 'flex', alignItems: 'center', padding: '0 20px',
        borderBottom: '0.5px solid var(--border)', gap: 8, flexShrink: 0,
      }}>
        <span style={{ fontSize: 12, color: 'var(--text-muted)', flex: 1 }}>Project agent</span>
        {activeSkills.length > 0 && (
          <span style={{ fontSize: 11, color: 'var(--brand-light)' }}>✨ {activeSkills.join(', ')}</span>
        )}
        {BrowserTTS.isSupported() && (
          <button title="Read replies aloud" onClick={() => { setReadAloud(v => { const next = !v; readAloudRef.current = next; if (!next) ttsRef.current.cancel(); return next }) }}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11,
              color: readAloud ? 'var(--brand-light)' : 'var(--text-muted)', background: 'var(--bg-tertiary)',
              padding: '2px 8px', borderRadius: 99, border: '0.5px solid var(--border)', cursor: 'pointer' }}>
            {readAloud ? <Volume2 size={11} /> : <VolumeX size={11} />} Aloud
          </button>
        )}
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: '20%', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 28, marginBottom: 12 }}>✦</div>
            <div style={{ fontSize: 15, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>
              What are we building?
            </div>
            <div style={{ fontSize: 13 }}>
              Ask about this project. Agents can read files, research, write code, and validate output.
            </div>
          </div>
        )}
        <div style={{ maxWidth: 760, margin: '0 auto' }}>
          {messages.map(msg => <MessageBubble key={msg.id} msg={msg} />)}
          <div ref={bottomRef} />
        </div>
      </div>

      <div style={{
        padding: '12px 20px 16px',
        borderTop: '0.5px solid var(--border)',
        background: 'var(--bg-primary)'
      }}>
        <div style={{ maxWidth: 760, margin: '0 auto' }}>
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
            placeholder="Ask about your project, request code changes, research…"
            disabled={isStreaming}
            style={{
              flex: 1, border: 'none', outline: 'none', resize: 'none',
              background: 'transparent', fontSize: 14, lineHeight: 1.6,
              color: 'var(--text-primary)', height: 44, maxHeight: 160,
              fontFamily: 'inherit'
            }}
          />
          <div style={{ display: 'flex', gap: 6, alignItems: 'flex-end', paddingBottom: 2 }}>
            <button
              title="Attach file"
              onClick={() => fileRef.current?.click()}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
            >
              <Paperclip size={16} />
            </button>
            <MicButton onText={(t) => setInput(prev => (prev ? prev + ' ' : '') + t)} disabled={isStreaming} />
            <button
              onClick={send}
              disabled={isStreaming || (!input.trim() && attachments.length === 0)}
              style={{
                width: 32, height: 32, borderRadius: 8, border: 'none', cursor: isStreaming || (!input.trim() && attachments.length === 0) ? 'default' : 'pointer',
                background: isStreaming || (!input.trim() && attachments.length === 0) ? 'var(--bg-hover)' : 'var(--brand-dark)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                transition: 'background 0.15s'
              }}
            >
              {isStreaming
                ? <span style={{ width: 12, height: 12, borderRadius: 2, background: 'var(--text-muted)' }} />
                : <ArrowUp size={15} color={input.trim() || attachments.length > 0 ? 'white' : 'var(--text-muted)'} />
              }
            </button>
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6, textAlign: 'center' }}>
          Enter to send · Shift+Enter for new line · Project agents can read and write project files
        </div>
        </div>
      </div>
    </div>
  )
}

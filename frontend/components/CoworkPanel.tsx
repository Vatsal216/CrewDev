'use client'
import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Square, Eye, Pencil, Paperclip, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useStore, Message } from '@/lib/store'
import { api, CoworkSocket } from '@/lib/api'
import ModelPicker from '@/components/ModelPicker'
import MicButton from '@/components/MicButton'
import CodeBlock from '@/components/CodeBlock'

export default function CoworkPanel({ sessionId }: { sessionId: string }) {
  const { messages, setMessages, addMessage, isStreaming, setStreaming, setErrorMessage, coworkSessions, updateCoworkSession } = useStore()
  const [input, setInput] = useState('')
  const [activeSkills, setActiveSkills] = useState<string[]>([])
  const [attachments, setAttachments] = useState<{ name: string; kind: string; text?: string; data_url?: string }[]>([])
  const [doc, setDoc] = useState('')
  const [preview, setPreview] = useState(false)
  const [docNote, setDocNote] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const socketRef = useRef<CoworkSocket | null>(null)
  const streamBufRef = useRef('')
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const session = coworkSessions.find(s => s.id === sessionId)

  // load messages + doc
  useEffect(() => {
    let cancelled = false
    setStreaming(false); setErrorMessage(null); streamBufRef.current = ''
    api.cowork.messages(sessionId).then(msgs => {
      if (!cancelled) setMessages(msgs.map(m => ({ id: m.id, role: m.role, content: m.content })))
    }).catch(() => { if (!cancelled) setMessages([]) })
    api.cowork.get(sessionId).then(s => { if (!cancelled) setDoc(s.doc_content || '') }).catch(() => {})
    return () => { cancelled = true }
  }, [sessionId, setMessages, setStreaming, setErrorMessage])

  // socket
  useEffect(() => {
    const sock = new CoworkSocket(sessionId)
    sock.connect()
    socketRef.current = sock
    const off = sock.on((event) => {
      if (event.type === 'skills_activated') {
        setActiveSkills(event.names || [])
        return
      }
      if (event.type === 'token') {
        streamBufRef.current += event.text || ''
        const buf = streamBufRef.current
        setMessages(prev => {
          const safe = Array.isArray(prev) ? prev : []
          const hasStreaming = safe.some(m => m.streaming)
          if (hasStreaming) return safe.map(m => m.streaming ? { ...m, content: buf } : m)
          return [...safe, { id: 'streaming-cowork', role: 'assistant', content: buf, streaming: true }]
        })
      } else if (event.type === 'doc_update') {
        setDoc(event.doc || '')
        setDocNote('Agent updated the doc')
        setTimeout(() => setDocNote(''), 2500)
      } else if (event.type === 'final') {
        const finalText = event.content || streamBufRef.current || 'Done.'
        streamBufRef.current = ''
        setMessages(prev => (Array.isArray(prev) ? prev : []).filter(m => !m.streaming).concat({ id: event.id || `a-${Date.now()}`, role: 'assistant', content: finalText }))
        setStreaming(false)
      } else if (event.type === 'error') {
        setErrorMessage(event.message || 'Cowork error.')
        setStreaming(false)
      }
    })
    return () => { off(); sock.disconnect(); if (socketRef.current === sock) socketRef.current = null }
  }, [sessionId, setMessages, setStreaming, setErrorMessage])

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  function onDocChange(value: string) {
    setDoc(value)
    if (saveTimer.current) clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => { api.cowork.saveDoc(sessionId, value).catch(() => {}) }, 700)
  }

  function send() {
    const text = input.trim()
    if (!text && attachments.length === 0) return
    if (isStreaming) return
    setInput(''); setActiveSkills([]); streamBufRef.current = ''
    addMessage({ id: `u-${Date.now()}`, role: 'user', content: text })
    setStreaming(true)
    socketRef.current?.send(text, attachments)
    setAttachments([])
  }

  return (
    <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minWidth: 0 }}>
      {/* Chat (left) */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0, borderRight: '0.5px solid var(--border)' }}>
        <div style={{ height: 46, display: 'flex', alignItems: 'center', gap: 10, padding: '0 20px', borderBottom: '0.5px solid var(--border)', flexShrink: 0 }}>
          <span style={{ fontSize: 13, fontWeight: 500 }}>{session?.title || 'Workspace'}</span>
          {activeSkills.length > 0 && (
            <span style={{ fontSize: 11, color: 'var(--brand-light)' }}>✨ {activeSkills.join(', ')}</span>
          )}
          <div style={{ marginLeft: 'auto' }}>
            <ModelPicker
              providerId={session?.model_provider_id ?? null}
              model={session?.model ?? null}
              onChange={async (providerId, model) => {
                const updated = await api.cowork.update(sessionId, { model_provider_id: providerId, model })
                updateCoworkSession(sessionId, updated)
              }}
            />
          </div>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
          <div style={{ maxWidth: 720, margin: '0 auto' }}>
            {messages.map(m => (
              <div key={m.id} style={{ marginBottom: 18 }}>
                {m.role === 'user'
                  ? <div style={{ display: 'flex', justifyContent: 'flex-end' }}><div style={{ maxWidth: '85%', background: 'rgba(217,119,87,0.12)', border: '0.5px solid rgba(217,119,87,0.22)', borderRadius: 12, padding: '10px 14px', fontSize: 14, whiteSpace: 'pre-wrap' }}>{m.content}</div></div>
                  : <div className="prose-dark"><ReactMarkdown remarkPlugins={[remarkGfm]} components={{ pre: ({ children }: any) => <>{children}</>, code: CodeBlock }}>{m.content || ''}</ReactMarkdown></div>}
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>
        <div style={{ padding: '12px 20px 16px', borderTop: '0.5px solid var(--border)' }}>
          <div style={{ maxWidth: 720, margin: '0 auto' }}>
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
            <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', border: '0.5px solid var(--border-strong)', borderRadius: 14, background: 'var(--bg-secondary)', padding: '8px 12px' }}>
              <textarea value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
                placeholder="Work with the agent on the doc…" disabled={isStreaming}
                style={{ flex: 1, border: 'none', outline: 'none', resize: 'none', background: 'transparent', fontSize: 14, lineHeight: 1.6, color: 'var(--text-primary)', height: 44, maxHeight: 180, fontFamily: 'inherit' }} />
              <button
                title="Attach file"
                onClick={() => fileRef.current?.click()}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 4 }}
              >
                <Paperclip size={16} />
              </button>
              <MicButton onText={(t) => setInput(prev => (prev ? prev + ' ' : '') + t)} disabled={isStreaming} />
              <button onClick={send} disabled={!input.trim() && attachments.length === 0 && !isStreaming} style={{ width: 32, height: 32, borderRadius: 8, border: 'none', cursor: 'pointer', background: input.trim() || attachments.length > 0 ? 'var(--brand-dark)' : 'var(--bg-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {isStreaming ? <Square size={13} color="white" /> : <ArrowUp size={15} color={input.trim() || attachments.length > 0 ? 'white' : 'var(--text-muted)'} />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Doc (right) */}
      <div style={{ width: 460, minWidth: 320, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg-secondary)' }}>
        <div style={{ height: 46, display: 'flex', alignItems: 'center', gap: 8, padding: '0 16px', borderBottom: '0.5px solid var(--border)', flexShrink: 0 }}>
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Document</span>
          {docNote && <span style={{ fontSize: 11, color: 'var(--brand-light)' }}>{docNote}</span>}
          <button onClick={() => setPreview(p => !p)} title={preview ? 'Edit' : 'Preview'}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            {preview ? <Pencil size={14} /> : <Eye size={14} />}
          </button>
        </div>
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {preview
            ? <div className="prose-dark"><ReactMarkdown remarkPlugins={[remarkGfm]}>{doc || '_(empty)_'}</ReactMarkdown></div>
            : <textarea value={doc} onChange={e => onDocChange(e.target.value)} placeholder="The shared document…"
                style={{ width: '100%', height: '100%', minHeight: 400, border: 'none', outline: 'none', resize: 'none', background: 'transparent', color: 'var(--text-primary)', fontFamily: "'JetBrains Mono', monospace", fontSize: 13, lineHeight: 1.6 }} />}
        </div>
      </div>
    </div>
  )
}

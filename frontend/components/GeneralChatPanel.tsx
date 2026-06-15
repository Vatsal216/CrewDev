'use client'
import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Bot, Brain, Globe2, Paperclip, Square, Volume2, VolumeX, X } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useStore, Message } from '@/lib/store'
import { api, GeneralChatSocket } from '@/lib/api'
import ModelPicker from '@/components/ModelPicker'
import MicButton from '@/components/MicButton'
import { BrowserTTS } from '@/lib/voice'
import CodeBlock from '@/components/CodeBlock'

function MessageBubble({ msg }: { msg: Message }) {
  if (msg.role === 'user') {
    return (
      <div style={{ marginBottom: 20, display: 'flex', justifyContent: 'flex-end' }}>
        <div style={{ maxWidth: '85%' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 5, textAlign: 'right' }}>You</div>
          <div style={{
            background: 'rgba(217,119,87,0.12)', border: '0.5px solid rgba(217,119,87,0.22)',
            borderRadius: 12, padding: '10px 14px', fontSize: 14,
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
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>CrewDev Chat</span>
      </div>
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

interface GeneralChatPanelProps {
  chatId: string
}

export default function GeneralChatPanel({ chatId }: GeneralChatPanelProps) {
  const {
    messages, setMessages, addMessage, isStreaming, setStreaming, setUsage,
    setErrorMessage, generalChats, updateGeneralChat
  } = useStore()
  const [input, setInput] = useState('')
  const [activeSkills, setActiveSkills] = useState<string[]>([])
  const [webStatus, setWebStatus] = useState<string | null>(null)
  const [agentStatus, setAgentStatus] = useState<string | null>(null)
  const [attachments, setAttachments] = useState<{ name: string; kind: string; text?: string; data_url?: string }[]>([])
  const [readAloud, setReadAloud] = useState(false)
  const readAloudRef = useRef(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const socketRef = useRef<GeneralChatSocket | null>(null)
  const streamBufRef = useRef('')
  const ttsRef = useRef(new BrowserTTS())
  const chat = generalChats.find(c => c.id === chatId)

  useEffect(() => {
    let cancelled = false
    setStreaming(false)
    setUsage(null)
    setErrorMessage(null)
    setAgentStatus(null)
    streamBufRef.current = ''

    api.chats.messages(chatId).then(msgs => {
      if (cancelled) return
      setMessages(msgs.map(m => ({
        id: m.id,
        role: m.role,
        content: m.content,
        meta: m.meta,
        created_at: m.created_at,
      })))
    }).catch(error => {
      if (!cancelled) {
        setMessages([])
        setErrorMessage(`Unable to load chat history: ${error.message}`)
      }
    })

    return () => { cancelled = true }
  }, [chatId, setMessages, setStreaming, setUsage, setErrorMessage])

  useEffect(() => {
    const sock = new GeneralChatSocket(chatId)
    sock.connect()
    socketRef.current = sock

    const off = sock.on((event) => {
      if (event.type === 'mode') {
        setAgentStatus(event.mode === 'agent' ? 'Agent mode active' : null)
        return
      }

      if (event.type === 'agent_status') {
        setAgentStatus(event.message || null)
        return
      }

      if (event.type === 'agent_plan') {
        const steps = Array.isArray(event.steps) ? event.steps.length : 0
        const tools = Array.isArray(event.tools) ? event.tools.length : 0
        setAgentStatus(`Agent planned ${steps} step${steps === 1 ? '' : 's'}${tools ? ` · ${tools} tool call${tools === 1 ? '' : 's'}` : ''}`)
        return
      }

      if (event.type === 'tool_call') {
        setAgentStatus(`Using ${event.tool || 'tool'}…`)
        return
      }

      if (event.type === 'tool_result') {
        setAgentStatus(event.ok === false ? `${event.tool || 'Tool'} failed; continuing` : `${event.tool || 'Tool'} complete`)
        return
      }

      if (event.type === 'web_search') {
        if (event.ok === false) setWebStatus('Web search unavailable — add a Tavily key in Settings')
        else if (event.ok === true) setWebStatus(null)
        else setWebStatus('Searching the web…')
        return
      }

      if (event.type === 'token') {
        setWebStatus(null)
        streamBufRef.current += event.text || ''
        const buf = streamBufRef.current
        setMessages(prev => {
          const safePrev = Array.isArray(prev) ? prev : []
          const hasStreaming = safePrev.some(m => m.streaming)
          if (hasStreaming) return safePrev.map(m => m.streaming ? { ...m, content: buf } : m)
          return [...safePrev, { id: 'streaming-general', role: 'assistant', content: buf, streaming: true }]
        })
        return
      }

      if (event.type === 'final') {
        const finalText = event.content || streamBufRef.current || 'Done.'
        streamBufRef.current = ''
        setMessages(prev => {
          const safePrev = Array.isArray(prev) ? prev : []
          return safePrev.filter(m => !m.streaming).concat({
            id: event.id || `assistant-${Date.now()}`,
            role: 'assistant',
            content: finalText,
            meta: event.meta || {},
          })
        })
        if (event.chat_title) updateGeneralChat(chatId, { title: event.chat_title })
        setStreaming(false)
        setAgentStatus(null)
        if (readAloudRef.current) ttsRef.current.speak(finalText)
        return
      }

      if (event.type === 'memory_saved') {
        return
      }

      if (event.type === 'skills_activated') {
        setActiveSkills(event.names || [])
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
        const message = event.message || 'Unknown chat error.'
        setMessages(prev => {
          const safePrev = Array.isArray(prev) ? prev : []
          return safePrev.filter(m => !m.streaming).concat({
            id: `error-${Date.now()}`,
            role: 'assistant',
            content: `Error: ${message}`,
          })
        })
        setErrorMessage(message)
        setStreaming(false)
        setWebStatus(null)
        setAgentStatus(null)
      }
    })

    return () => {
      off()
      sock.disconnect()
      if (socketRef.current === sock) socketRef.current = null
      ttsRef.current.cancel()
    }
  }, [chatId, setMessages, setStreaming, setUsage, setErrorMessage, updateGeneralChat])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function send() {
    const text = input.trim()
    if (!text && attachments.length === 0) return
    if (isStreaming) return
    setInput('')
    setActiveSkills([])
    setWebStatus(null)
    setAgentStatus(chat?.agent_enabled ? 'Agent mode active' : null)
    setErrorMessage(null)
    streamBufRef.current = ''
    addMessage({ id: `user-${Date.now()}`, role: 'user', content: text })
    setStreaming(true)
    socketRef.current?.send(text, attachments)
    setAttachments([])
    if (textareaRef.current) textareaRef.current.style.height = '44px'
  }

  function stop() {
    socketRef.current?.disconnect()
    setStreaming(false)
    setAgentStatus(null)
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
        borderBottom: '0.5px solid var(--border)', gap: 10, flexShrink: 0
      }}>
        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>
          {chat?.title || 'New chat'}
        </span>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11,
          color: chat?.memory_enabled ? 'var(--green)' : 'var(--text-muted)',
          background: 'var(--bg-tertiary)', padding: '2px 8px', borderRadius: 99,
          border: '0.5px solid var(--border)'
        }}>
          <Brain size={11} /> Memory {chat?.memory_enabled ? 'on' : 'off'}
        </span>
        <button
          title="Toggle live web search & browsing for this chat"
          onClick={async () => {
            try {
              const updated = await api.chats.update(chatId, { web_enabled: !chat?.web_enabled })
              updateGeneralChat(chatId, updated)
            } catch (e: any) {
              setErrorMessage(`Could not toggle web: ${e?.message || e}`)
            }
          }}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11,
            color: chat?.web_enabled ? 'var(--brand-light)' : 'var(--text-muted)',
            background: 'var(--bg-tertiary)', padding: '2px 8px', borderRadius: 99,
            border: '0.5px solid var(--border)', cursor: 'pointer'
          }}>
          <Globe2 size={11} /> Web {chat?.web_enabled ? 'on' : 'off'}
        </button>
        <button
          title="Toggle Agent Mode for this chat"
          onClick={async () => {
            try {
              const next = !chat?.agent_enabled
              const updated = await api.chats.update(chatId, { agent_enabled: next, mode: next ? 'agent' : 'direct' })
              updateGeneralChat(chatId, updated)
              setAgentStatus(next ? 'Agent mode enabled' : null)
            } catch (e: any) {
              setErrorMessage(`Could not toggle agent mode: ${e?.message || e}`)
            }
          }}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11,
            color: chat?.agent_enabled ? 'var(--brand-light)' : 'var(--text-muted)',
            background: 'var(--bg-tertiary)', padding: '2px 8px', borderRadius: 99,
            border: '0.5px solid var(--border)', cursor: 'pointer'
          }}>
          <Bot size={11} /> Agent {chat?.agent_enabled ? 'on' : 'off'}
        </button>
        {BrowserTTS.isSupported() && (
          <button title="Read replies aloud" onClick={() => { setReadAloud(v => { const next = !v; readAloudRef.current = next; if (!next) ttsRef.current.cancel(); return next }) }}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11,
              color: readAloud ? 'var(--brand-light)' : 'var(--text-muted)', background: 'var(--bg-tertiary)',
              padding: '2px 8px', borderRadius: 99, border: '0.5px solid var(--border)', cursor: 'pointer' }}>
            {readAloud ? <Volume2 size={11} /> : <VolumeX size={11} />} Aloud
          </button>
        )}
        <ModelPicker
          providerId={chat?.model_provider_id ?? null}
          model={chat?.model ?? null}
          onChange={async (providerId, model) => {
            const updated = await api.chats.update(chatId, { model_provider_id: providerId, model })
            updateGeneralChat(chatId, updated)
          }}
        />
        {activeSkills.length > 0 && (
          <span style={{ fontSize: 11, color: 'var(--brand-light)' }}>✨ {activeSkills.join(', ')}</span>
        )}
        {webStatus && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--brand-light)' }}>
            <Globe2 size={11} /> {webStatus}
          </span>
        )}
        {agentStatus && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11, color: 'var(--brand-light)' }}>
            <Bot size={11} /> {agentStatus}
          </span>
        )}
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {messages.length === 0 && (
          <div style={{ textAlign: 'center', marginTop: '18%', color: 'var(--text-muted)' }}>
            <div style={{ fontSize: 30, marginBottom: 12 }}>✦</div>
            <div style={{ fontSize: 16, fontWeight: 500, color: 'var(--text-secondary)', marginBottom: 6 }}>
              How can I help?
            </div>
            <div style={{ fontSize: 13, maxWidth: 420, margin: '0 auto', lineHeight: 1.6 }}>
              General chat is separate from Projects. Use Direct mode for fast replies or Agent mode for planning and tool-assisted research.
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
          border: '0.5px solid var(--border-strong)', borderRadius: 14,
          background: 'var(--bg-secondary)', padding: '8px 12px'
        }}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={onInput}
            onKeyDown={onKeyDown}
            placeholder="Message CrewDev…"
            disabled={isStreaming}
            style={{
              flex: 1, border: 'none', outline: 'none', resize: 'none',
              background: 'transparent', fontSize: 14, lineHeight: 1.6,
              color: 'var(--text-primary)', height: 44, maxHeight: 180,
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
              onClick={isStreaming ? stop : send}
              disabled={!isStreaming && !input.trim() && attachments.length === 0}
              style={{
                width: 32, height: 32, borderRadius: 8, border: 'none',
                cursor: !isStreaming && !input.trim() && attachments.length === 0 ? 'default' : 'pointer',
                background: !isStreaming && !input.trim() && attachments.length === 0 ? 'var(--bg-hover)' : 'var(--brand-dark)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}
            >
              {isStreaming
                ? <Square size={13} color="white" />
                : <ArrowUp size={15} color={input.trim() || attachments.length > 0 ? 'white' : 'var(--text-muted)'} />
              }
            </button>
          </div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6, textAlign: 'center' }}>
          Enter to send · Shift+Enter for new line · Agent mode uses planning and safe chat tools only
        </div>
        </div>
      </div>
    </div>
  )
}

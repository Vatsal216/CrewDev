'use client'
import { useRef, useState } from 'react'
import { Mic, Square, Loader2 } from 'lucide-react'
import { BrowserSTT, getSttMode, recordAndTranscribe } from '@/lib/voice'

type State = 'idle' | 'listening' | 'processing'

export default function MicButton({ onText, disabled }: { onText: (t: string) => void; disabled?: boolean }) {
  const [state, setState] = useState<State>('idle')
  const sttRef = useRef<BrowserSTT | null>(null)
  const recRef = useRef<{ stop: () => Promise<string> } | null>(null)

  async function start() {
    const useBrowser = getSttMode() === 'browser' && BrowserSTT.isSupported()
    if (useBrowser) {
      const stt = new BrowserSTT()
      sttRef.current = stt
      setState('listening')
      stt.start(
        () => {},
        (final) => onText(final),
        () => { sttRef.current = null; setState('idle') },
      )
    } else {
      try {
        setState('listening')
        recRef.current = await recordAndTranscribe()
      } catch {
        setState('idle')
      }
    }
  }

  async function stop() {
    if (sttRef.current) { sttRef.current.stop(); sttRef.current = null; setState('idle'); return }
    if (recRef.current) {
      setState('processing')
      try { const text = await recRef.current.stop(); if (text) onText(text) } catch {}
      recRef.current = null
      setState('idle')
    }
  }

  const icon = state === 'processing'
    ? <Loader2 size={16} style={{ animation: 'spin 1s linear infinite' }} />
    : state === 'listening'
      ? <Square size={14} />
      : <Mic size={16} />

  return (
    <button
      title="Dictate"
      disabled={disabled || state === 'processing'}
      onClick={() => (state === 'idle' ? start() : stop())}
      style={{
        background: 'none', border: 'none', padding: 4,
        cursor: disabled ? 'default' : 'pointer',
        color: state === 'listening' ? 'var(--brand)' : 'var(--text-muted)',
      }}
    >
      {icon}
    </button>
  )
}

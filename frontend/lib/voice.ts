import { api } from '@/lib/api'

export type SttMode = 'browser' | 'server'
const STT_KEY = 'crewdev.sttMode'

export function getSttMode(): SttMode {
  if (typeof window === 'undefined') return 'browser'
  return (localStorage.getItem(STT_KEY) as SttMode) || 'browser'
}
export function setSttMode(mode: SttMode) {
  if (typeof window !== 'undefined') localStorage.setItem(STT_KEY, mode)
}

function getSR(): any {
  if (typeof window === 'undefined') return null
  return (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition || null
}

export class BrowserSTT {
  private rec: any = null
  static isSupported(): boolean { return !!getSR() }

  start(onInterim: (t: string) => void, onFinal: (t: string) => void, onError: (e: string) => void) {
    const SR = getSR()
    if (!SR) { onError('unsupported'); return }
    const rec = new SR()
    rec.continuous = false
    rec.interimResults = true
    rec.lang = 'en-US'
    rec.onresult = (e: any) => {
      let interim = '', final = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const t = e.results[i][0].transcript
        if (e.results[i].isFinal) final += t
        else interim += t
      }
      if (interim) onInterim(interim)
      if (final) onFinal(final)
    }
    rec.onerror = (e: any) => onError(e.error || 'error')
    rec.start()
    this.rec = rec
  }

  stop() { try { this.rec?.stop() } catch {} this.rec = null }
}

export class BrowserTTS {
  static isSupported(): boolean {
    return typeof window !== 'undefined' && 'speechSynthesis' in window
  }
  speak(text: string) {
    if (!BrowserTTS.isSupported() || !text) return
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text))
  }
  cancel() { if (BrowserTTS.isSupported()) window.speechSynthesis.cancel() }
}

export async function recordAndTranscribe(): Promise<{ stop: () => Promise<string> }> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
  const chunks: BlobPart[] = []
  const rec = new MediaRecorder(stream)
  rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data) }
  rec.start()
  return {
    stop: () => new Promise<string>((resolve, reject) => {
      rec.onstop = async () => {
        stream.getTracks().forEach(t => t.stop())
        try {
          const blob = new Blob(chunks, { type: 'audio/webm' })
          const { text } = await api.voice.transcribe(blob)
          resolve(text || '')
        } catch (err) { reject(err) }
      }
      try { rec.stop() } catch (err) { reject(err) }
    }),
  }
}

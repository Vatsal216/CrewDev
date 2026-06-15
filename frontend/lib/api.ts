const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const WS = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'

// ─── REST ──────────────────────────────────────────────────────

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
  return res.json()
}

export const api = {
  projects: {
    list: () => req<any[]>('/api/projects'),
    create: (name: string, description?: string) =>
      req<any>('/api/projects', { method: 'POST', body: JSON.stringify({ name, description }) }),
    get: (id: string) => req<any>(`/api/projects/${id}`),
    delete: (id: string) => req(`/api/projects/${id}`, { method: 'DELETE' }),
    files: (id: string) => req<{ tree: any[] }>(`/api/projects/${id}/files`),
    index: (id: string) => req(`/api/projects/${id}/index`, { method: 'POST' }),
    upload: async (id: string, files: FileList) => {
      const form = new FormData()
      Array.from(files).forEach(f => form.append('files', f))
      const res = await fetch(`${API}/api/projects/${id}/upload`, { method: 'POST', body: form })
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
      return res.json()
    },
  },
  sessions: {
    create: (projectId: string) => req<any>(`/api/projects/${projectId}/sessions`, { method: 'POST' }),
    list: (projectId: string) => req<any[]>(`/api/projects/${projectId}/sessions`),
    messages: (sessionId: string) => req<any[]>(`/api/sessions/${sessionId}/messages`),
    update: (projectId: string, sessionId: string, data: Record<string, any>) =>
      req<any>(`/api/projects/${projectId}/sessions/${sessionId}`, {
        method: 'PATCH', body: JSON.stringify(data),
      }),
  },
  chats: {
    create: (title?: string) => req<any>('/api/chats', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
    list: () => req<any[]>('/api/chats'),
    get: (id: string) => req<any>(`/api/chats/${id}`),
    update: (id: string, data: Record<string, any>) => req<any>(`/api/chats/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),
    delete: (id: string) => req<{ ok: boolean }>(`/api/chats/${id}`, { method: 'DELETE' }),
    messages: (id: string) => req<any[]>(`/api/chats/${id}/messages`),
    memories: () => req<any[]>('/api/chat-memory'),
    deleteMemory: (id: string) => req<{ ok: boolean }>(`/api/chat-memory/${id}`, { method: 'DELETE' }),
  },
  providers: {
    list: () => req<any[]>('/api/providers'),
    create: (data: { provider: string; label: string; config: Record<string, any>; enabled?: boolean; is_default?: boolean }) =>
      req<any>('/api/providers', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, any>) =>
      req<any>(`/api/providers/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) => req<{ ok: boolean }>(`/api/providers/${id}`, { method: 'DELETE' }),
    test: (id: string) => req<{ ok: boolean; code: string; message: string }>(`/api/providers/${id}/test`, { method: 'POST' }),
    models: (id: string) => req<{ models: string[] }>(`/api/providers/${id}/models`),
  },
  settings: {
    getDefaultModel: () => req<{ value: string | null }>('/api/settings/default-model'),
    setDefaultModel: (value: string) =>
      req<{ value: string }>('/api/settings/default-model', { method: 'PUT', body: JSON.stringify({ value }) }),
  },
  voice: {
    transcribe: async (blob: Blob): Promise<{ text: string }> => {
      const form = new FormData()
      form.append('audio', blob, 'audio.webm')
      const res = await fetch(`${API}/api/voice/transcribe`, { method: 'POST', body: form })
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
      return res.json()
    },
  },
  code: {
    create: (title?: string) => req<any>('/api/code', { method: 'POST', body: JSON.stringify({ title }) }),
    list: () => req<any[]>('/api/code'),
    get: (id: string) => req<any>(`/api/code/${id}`),
    update: (id: string, data: Record<string, any>) => req<any>(`/api/code/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) => req<{ ok: boolean }>(`/api/code/${id}`, { method: 'DELETE' }),
    messages: (id: string) => req<any[]>(`/api/code/${id}/messages`),
  },
  cowork: {
    create: (title?: string) => req<any>('/api/cowork', { method: 'POST', body: JSON.stringify({ title }) }),
    list: () => req<any[]>('/api/cowork'),
    get: (id: string) => req<any>(`/api/cowork/${id}`),
    update: (id: string, data: Record<string, any>) => req<any>(`/api/cowork/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) => req<{ ok: boolean }>(`/api/cowork/${id}`, { method: 'DELETE' }),
    messages: (id: string) => req<any[]>(`/api/cowork/${id}/messages`),
    saveDoc: (id: string, content: string) => req<{ ok: boolean }>(`/api/cowork/${id}/doc`, { method: 'PUT', body: JSON.stringify({ content }) }),
  },
  skills: {
    list: () => req<any[]>('/api/skills'),
    create: (data: { name: string; description?: string; instructions?: string; enabled?: boolean }) =>
      req<any>('/api/skills', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: string, data: Record<string, any>) =>
      req<any>(`/api/skills/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
    delete: (id: string) => req<{ ok: boolean }>(`/api/skills/${id}`, { method: 'DELETE' }),
  },
  exec: {
    run: (code: string) => req<{
      run_id: string; stdout: string; stderr: string; exit_code: number;
      timed_out: boolean; artifacts: { name: string; is_image: boolean }[]
    }>('/api/exec', { method: 'POST', body: JSON.stringify({ code }) }),
    artifactUrl: (runId: string, name: string) => `${API}/api/exec/${runId}/artifact/${encodeURIComponent(name)}`,
  },
  attachments: {
    upload: async (files: FileList | File[]): Promise<{ name: string; kind: string; text?: string; data_url?: string }[]> => {
      const form = new FormData()
      Array.from(files).forEach(f => form.append('files', f))
      const res = await fetch(`${API}/api/attachments`, { method: 'POST', body: form })
      if (!res.ok) throw new Error(`${res.status} ${await res.text()}`)
      return res.json()
    },
  },
}

// ─── WebSocket ─────────────────────────────────────────────────

type Listener = (event: any) => void

class ReliableSocket {
  protected ws: WebSocket | null = null
  private listeners: Listener[] = []
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private sendQueue: string[] = []
  private manuallyClosed = false
  private url: string

  constructor(url: string) {
    this.url = url
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) return
    this.manuallyClosed = false
    this.ws = new WebSocket(this.url)

    this.ws.onopen = () => {
      const queued = [...this.sendQueue]
      this.sendQueue = []
      queued.forEach(payload => this.ws?.send(payload))
    }

    this.ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        this.listeners.forEach(fn => fn(data))
      } catch {
        this.listeners.forEach(fn => fn({ type: 'error', message: 'Invalid WebSocket message received.' }))
      }
    }

    this.ws.onclose = () => {
      if (!this.manuallyClosed) {
        this.reconnectTimer = setTimeout(() => this.connect(), 2000)
      }
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  send(content: string, attachments: any[] = []) {
    const payload = JSON.stringify({ content, attachments })
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(payload)
      return
    }
    this.sendQueue.push(payload)
    this.connect()
  }

  on(listener: Listener) {
    this.listeners.push(listener)
    return () => { this.listeners = this.listeners.filter(l => l !== listener) }
  }

  disconnect() {
    this.manuallyClosed = true
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
    this.sendQueue = []
    this.ws?.close()
    this.ws = null
  }
}

export class ChatSocket extends ReliableSocket {
  constructor(projectId: string, sessionId: string) {
    super(`${WS}/ws/${projectId}/${sessionId}`)
  }
}

export class GeneralChatSocket extends ReliableSocket {
  constructor(chatId: string) {
    super(`${WS}/ws/chats/${chatId}`)
  }
}

export class CoworkSocket extends ReliableSocket {
  constructor(sessionId: string) {
    super(`${WS}/ws/cowork/${sessionId}`)
  }
}

export class CodeSocket extends ReliableSocket {
  constructor(sessionId: string) {
    super(`${WS}/ws/code/${sessionId}`)
  }
}

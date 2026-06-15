import { create } from 'zustand'

export interface Project {
  id: string
  name: string
  description: string
  indexed: boolean
  index_status: string
  created_at: string
}

export interface Provider {
  id: string
  provider: 'anthropic' | 'openai' | 'azure' | 'ollama'
  label: string
  enabled: boolean
  is_default: boolean
  has_key: boolean
  key_masked: string
  config: Record<string, any>
}

export interface CoworkSession {
  id: string
  title: string
  doc_content: string
  model?: string | null
  model_provider_id?: string | null
}

export interface CodeSession {
  id: string
  title: string
  project_id: string
  chat_session_id: string
  model?: string | null
  model_provider_id?: string | null
  engine: 'crewai' | 'deepagents'
  created_at: string
  updated_at: string
}

export interface GeneralChat {
  id: string
  title: string
  pinned: boolean
  archived: boolean
  memory_enabled: boolean
  web_enabled: boolean
  agent_enabled: boolean
  mode: 'direct' | 'agent'
  created_at: string
  updated_at: string
  model?: string | null
  model_provider_id?: string | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  meta?: { trace?: TraceEvent[]; sources?: any[]; [key: string]: any }
  created_at?: string
  streaming?: boolean
}

export interface TraceEvent {
  type: string
  message?: string
  agent_type?: string
  task_id?: string
  description?: string
  passed?: boolean
  score?: number
  feedback?: string
  attempt?: number
  text?: string
  subtasks?: Array<{ id: string; agent_type: string; description: string; depends_on?: string[] }>
  cost_usd?: number
  total_tokens?: number
  [key: string]: any
}

export interface Usage {
  total_tokens: number
  cost_usd: number
  calls: number
}

export interface FileNode {
  type: 'file' | 'dir'
  name: string
  path: string
  size?: number
  extension?: string
  children?: FileNode[]
}

export interface ChatMemory {
  id: string
  content: string
  memory_type: string
  enabled: boolean
  created_at: string
  updated_at: string
}

export interface Skill {
  id: string
  name: string
  description: string
  instructions: string
  enabled: boolean
}

type MessageUpdater = Message[] | ((prev: Message[]) => Message[])

interface AppState {
  activeMode: 'chat' | 'project' | 'cowork' | 'code'

  projects: Project[]
  activeProjectId: string | null
  activeSessionId: string | null

  generalChats: GeneralChat[]
  activeChatId: string | null
  chatMemories: ChatMemory[]

  coworkSessions: CoworkSession[]
  activeCoworkId: string | null

  codeSessions: CodeSession[]
  activeCodeId: string | null

  messages: Message[]
  fileTree: FileNode[]
  traceEvents: TraceEvent[]
  isStreaming: boolean
  indexingProjectId: string | null
  lastUsage: Usage | null
  errorMessage: string | null

  providers: Provider[]
  defaultModel: string | null
  setProviders: (p: Provider[]) => void
  setDefaultModel: (v: string | null) => void

  skills: Skill[]
  setSkills: (s: Skill[]) => void

  setActiveMode: (mode: 'chat' | 'project' | 'cowork' | 'code') => void

  setProjects: (p: Project[]) => void
  setActiveProject: (id: string | null) => void
  setActiveSession: (id: string | null) => void
  updateProject: (id: string, updates: Partial<Project>) => void
  addProject: (p: Project) => void

  setGeneralChats: (chats: GeneralChat[]) => void
  addGeneralChat: (chat: GeneralChat) => void
  updateGeneralChat: (id: string, updates: Partial<GeneralChat>) => void
  removeGeneralChat: (id: string) => void
  setActiveChat: (id: string | null) => void
  setChatMemories: (memories: ChatMemory[]) => void

  setCoworkSessions: (s: CoworkSession[]) => void
  addCoworkSession: (s: CoworkSession) => void
  updateCoworkSession: (id: string, updates: Partial<CoworkSession>) => void
  removeCoworkSession: (id: string) => void
  setActiveCowork: (id: string | null) => void

  setCodeSessions: (s: CodeSession[]) => void
  addCodeSession: (s: CodeSession) => void
  updateCodeSession: (id: string, updates: Partial<CodeSession>) => void
  removeCodeSession: (id: string) => void
  setActiveCode: (id: string | null) => void

  addMessage: (m: Message) => void
  setMessages: (msgs: MessageUpdater) => void
  appendTraceEvent: (e: TraceEvent) => void
  clearTrace: () => void
  setFileTree: (tree: FileNode[]) => void
  setStreaming: (v: boolean) => void
  setIndexingProject: (id: string | null) => void
  setUsage: (u: Usage | null) => void
  setErrorMessage: (message: string | null) => void
}

export const useStore = create<AppState>((set) => ({
  activeMode: 'project',

  providers: [],
  defaultModel: null,
  setProviders: (providers) => set({ providers }),
  setDefaultModel: (defaultModel) => set({ defaultModel }),

  skills: [],
  setSkills: (skills) => set({ skills }),

  projects: [],
  activeProjectId: null,
  activeSessionId: null,

  generalChats: [],
  activeChatId: null,
  chatMemories: [],

  coworkSessions: [],
  activeCoworkId: null,

  codeSessions: [],
  activeCodeId: null,

  messages: [],
  fileTree: [],
  traceEvents: [],
  isStreaming: false,
  indexingProjectId: null,
  lastUsage: null,
  errorMessage: null,

  setActiveMode: (activeMode) => set({
    activeMode,
    messages: [],
    traceEvents: [],
    lastUsage: null,
    errorMessage: null,
    isStreaming: false,
  }),

  setProjects: (projects) => set({ projects }),
  setActiveProject: (id) => set({
    activeMode: 'project',
    activeProjectId: id,
    activeChatId: null,
    activeCoworkId: null,
    activeCodeId: null,
    messages: [],
    fileTree: [],
    traceEvents: [],
    lastUsage: null,
    errorMessage: null,
    isStreaming: false,
  }),
  setActiveSession: (id) => set({ activeSessionId: id }),
  updateProject: (id, updates) => set((s) => ({
    projects: s.projects.map((p) => p.id === id ? { ...p, ...updates } : p)
  })),
  addProject: (p) => set((s) => ({ projects: [p, ...s.projects] })),

  setGeneralChats: (generalChats) => set({ generalChats }),
  addGeneralChat: (chat) => set((s) => ({ generalChats: [chat, ...s.generalChats] })),
  updateGeneralChat: (id, updates) => set((s) => ({
    generalChats: s.generalChats.map((c) => c.id === id ? { ...c, ...updates } : c)
  })),
  removeGeneralChat: (id) => set((s) => ({
    generalChats: s.generalChats.filter((c) => c.id !== id),
    activeChatId: s.activeChatId === id ? null : s.activeChatId,
    messages: s.activeChatId === id ? [] : s.messages,
  })),
  setActiveChat: (id) => set({
    activeMode: 'chat',
    activeChatId: id,
    activeProjectId: null,
    activeSessionId: null,
    activeCoworkId: null,
    activeCodeId: null,
    messages: [],
    traceEvents: [],
    lastUsage: null,
    errorMessage: null,
    isStreaming: false,
  }),
  setChatMemories: (chatMemories) => set({ chatMemories }),

  setCoworkSessions: (coworkSessions) => set({ coworkSessions }),
  addCoworkSession: (s) => set((state) => ({ coworkSessions: [s, ...state.coworkSessions] })),
  updateCoworkSession: (id, updates) => set((state) => ({
    coworkSessions: state.coworkSessions.map((s) => s.id === id ? { ...s, ...updates } : s)
  })),
  removeCoworkSession: (id) => set((state) => ({
    coworkSessions: state.coworkSessions.filter((s) => s.id !== id),
    activeCoworkId: state.activeCoworkId === id ? null : state.activeCoworkId,
    messages: state.activeCoworkId === id ? [] : state.messages,
  })),
  setActiveCowork: (id) => set({
    activeMode: 'cowork',
    activeCoworkId: id,
    activeProjectId: null,
    activeChatId: null,
    activeCodeId: null,
    messages: [],
    traceEvents: [],
    lastUsage: null,
    errorMessage: null,
    isStreaming: false,
  }),

  setCodeSessions: (codeSessions) => set({ codeSessions }),
  addCodeSession: (s) => set((state) => ({ codeSessions: [s, ...state.codeSessions] })),
  updateCodeSession: (id, updates) => set((state) => ({
    codeSessions: state.codeSessions.map((s) => s.id === id ? { ...s, ...updates } : s)
  })),
  removeCodeSession: (id) => set((state) => ({
    codeSessions: state.codeSessions.filter((s) => s.id !== id),
    activeCodeId: state.activeCodeId === id ? null : state.activeCodeId,
    messages: state.activeCodeId === id ? [] : state.messages,
  })),
  setActiveCode: (id) => set({
    activeMode: 'code',
    activeCodeId: id,
    activeProjectId: null,
    activeSessionId: null,
    activeChatId: null,
    activeCoworkId: null,
    messages: [],
    fileTree: [],
    traceEvents: [],
    lastUsage: null,
    errorMessage: null,
    isStreaming: false,
  }),

  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  setMessages: (next) => set((s) => ({
    messages: typeof next === 'function' ? next(s.messages) : next
  })),
  appendTraceEvent: (e) => set((s) => ({ traceEvents: [...s.traceEvents, e] })),
  clearTrace: () => set({ traceEvents: [] }),
  setFileTree: (fileTree) => set({ fileTree }),
  setStreaming: (isStreaming) => set({ isStreaming }),
  setIndexingProject: (indexingProjectId) => set({ indexingProjectId }),
  setUsage: (lastUsage) => set({ lastUsage }),
  setErrorMessage: (errorMessage) => set({ errorMessage }),
}))

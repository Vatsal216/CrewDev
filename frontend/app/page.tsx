'use client'
import { Zap, Plus, MessageSquare, Code2 } from 'lucide-react'
import Sidebar from '@/components/Sidebar'
import ChatPanel from '@/components/ChatPanel'
import GeneralChatPanel from '@/components/GeneralChatPanel'
import ChatRightPanel from '@/components/ChatRightPanel'
import RightPanel from '@/components/RightPanel'
import CoworkPanel from '@/components/CoworkPanel'
import CodePanel from '@/components/CodePanel'
import { useStore, Project, GeneralChat, CodeSession } from '@/lib/store'
import { api } from '@/lib/api'
import ModelPicker from '@/components/ModelPicker'

export default function Home() {
  const {
    activeMode, activeProjectId, activeSessionId, activeChatId, activeCoworkId, activeCodeId,
    setActiveProject, setActiveSession, setActiveChat, addGeneralChat,
    setGeneralChats, setMessages, setErrorMessage, setActiveCode, addCodeSession, codeSessions,
  } = useStore()

  async function handleSelectProject(project: Project) {
    setActiveProject(project.id)
    try {
      const sessions = await api.sessions.list(project.id)
      if (sessions.length > 0) {
        setActiveSession(sessions[0].id)
      } else {
        const session = await api.sessions.create(project.id)
        setActiveSession(session.id)
      }
    } catch (error: any) {
      setActiveSession(null)
      setErrorMessage(`Unable to open project: ${error.message}`)
    }
  }

  async function handleNewChat() {
    try {
      const chat = await api.chats.create()
      addGeneralChat(chat)
      setActiveChat(chat.id)
    } catch (error: any) {
      setErrorMessage(`Unable to create chat: ${error.message}`)
    }
  }

  async function handleSelectChat(chat: GeneralChat) {
    setActiveChat(chat.id)
  }

  async function handleNewCode() {
    try {
      const session = await api.code.create()
      addCodeSession(session)
      setActiveCode(session.id)
    } catch (error: any) {
      setErrorMessage(`Unable to create Code workspace: ${error.message}`)
    }
  }

  function handleSelectCode(session: CodeSession) {
    setActiveCode(session.id)
  }

  return (
    <div style={{
      display: 'flex', height: '100vh', overflow: 'hidden',
      background: 'var(--bg-primary)', color: 'var(--text-primary)'
    }}>
      <Sidebar
        onSelectProject={handleSelectProject}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onNewCode={handleNewCode}
        onSelectCode={handleSelectCode}
      />

      {activeMode === 'code' && activeCodeId ? (
        (() => {
          const session = codeSessions.find(s => s.id === activeCodeId)
          return session ? (
            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
              <CodePanel session={session} />
              <RightPanel projectId={session.project_id} />
            </div>
          ) : <CodeEmptyState onNewCode={handleNewCode} />
        })()
      ) : activeMode === 'cowork' && activeCoworkId ? (
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <CoworkPanel sessionId={activeCoworkId} />
        </div>
      ) : activeMode === 'chat' && activeChatId ? (
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <GeneralChatPanel chatId={activeChatId} />
          <ChatRightPanel />
        </div>
      ) : activeMode === 'project' && activeProjectId && activeSessionId ? (
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <TopBar projectId={activeProjectId} />
            <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
              <ChatPanel projectId={activeProjectId} sessionId={activeSessionId} />
              <RightPanel projectId={activeProjectId} />
            </div>
          </div>
        </div>
      ) : activeMode === 'code' ? (
        <CodeEmptyState onNewCode={handleNewCode} />
      ) : activeMode === 'chat' ? (
        <ChatEmptyState onNewChat={handleNewChat} />
      ) : (
        <ProjectEmptyState />
      )}
    </div>
  )
}

function TopBar({ projectId }: { projectId: string }) {
  const { projects, isStreaming, lastUsage, errorMessage, activeSessionId } = useStore()
  const project = projects.find(p => p.id === projectId)

  return (
    <div style={{
      height: 46, display: 'flex', alignItems: 'center', padding: '0 20px',
      borderBottom: '0.5px solid var(--border)', gap: 12, flexShrink: 0
    }}>
      <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: 7 }}>
        <Zap size={13} style={{ color: 'var(--brand)' }} />
        {project?.name || 'Project'}
      </span>
      {isStreaming && (
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: 11, color: 'var(--brand-light)',
          background: 'rgba(217,119,87,0.1)', padding: '2px 10px', borderRadius: 99
        }}>
          <span style={{
            width: 6, height: 6, borderRadius: '50%', background: 'var(--brand)',
            animation: 'pulse 1s ease-in-out infinite'
          }} />
          Agents running
        </span>
      )}
      {project?.indexed && (
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          fontSize: 11, color: 'var(--green)',
          background: 'rgba(29,158,117,0.1)', padding: '2px 10px', borderRadius: 99
        }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--green)' }} />
          Indexed
        </span>
      )}
      {errorMessage && (
        <span style={{
          fontSize: 11, color: 'var(--red)', background: 'rgba(216,90,48,0.1)',
          padding: '2px 10px', borderRadius: 99, maxWidth: 320, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap'
        }}>
          {errorMessage}
        </span>
      )}
      <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
        {activeSessionId && (
          <select
            defaultValue="crewai"
            onChange={(e) => api.sessions.update(projectId, activeSessionId, { engine: e.target.value }).catch(() => {})}
            style={{ fontSize: 11, padding: '3px 8px', borderRadius: 99, background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '0.5px solid var(--border)', cursor: 'pointer' }}
          >
            <option value="crewai">CrewAI</option>
            <option value="deepagents">DeepAgents</option>
          </select>
        )}
        {activeSessionId && (
          <ModelPicker
            providerId={null}
            model={null}
            onChange={(providerId, model) => {
              api.sessions.update(projectId, activeSessionId, { model_provider_id: providerId, model }).catch(() => {})
            }}
          />
        )}
        {lastUsage && (
          <span
            title={`${lastUsage.total_tokens.toLocaleString()} tokens · ${lastUsage.calls} LLM calls`}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 6,
              fontSize: 11, color: 'var(--text-secondary)',
              background: 'var(--bg-tertiary)', padding: '3px 10px', borderRadius: 99,
              border: '0.5px solid var(--border)'
            }}
          >
            <span style={{ color: 'var(--text-muted)' }}>last turn</span>
            <span style={{ fontWeight: 500, color: 'var(--text-primary)' }}>
              ${lastUsage.cost_usd.toFixed(4)}
            </span>
            <span style={{ color: 'var(--text-muted)' }}>
              · {(lastUsage.total_tokens / 1000).toFixed(1)}k tok
            </span>
          </span>
        )}
      </div>
    </div>
  )
}

function CodeEmptyState({ onNewCode }: { onNewCode: () => void }) {
  return (
    <div style={{
      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 16
    }}>
      <div style={{
        width: 56, height: 56, background: 'rgba(217,119,87,0.1)',
        borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: '0.5px solid rgba(217,119,87,0.3)'
      }}>
        <Code2 size={24} style={{ color: 'var(--brand)' }} />
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 17, fontWeight: 500, marginBottom: 6 }}>Start a Code workspace</div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 390, lineHeight: 1.6 }}>
          Code is a separate Claude Code-style pipeline. It can create files, edit code, run safe commands, and validate inside its own workspace.
        </div>
      </div>
      <button
        onClick={onNewCode}
        style={{
          display: 'flex', alignItems: 'center', gap: 7, padding: '8px 20px',
          background: 'var(--brand-dark)', border: 'none', borderRadius: 8,
          color: 'white', fontSize: 13, fontWeight: 500, cursor: 'pointer'
        }}
      >
        <Plus size={15} /> New Code workspace
      </button>
    </div>
  )
}

function ChatEmptyState({ onNewChat }: { onNewChat: () => void }) {
  return (
    <div style={{
      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 16
    }}>
      <div style={{
        width: 56, height: 56, background: 'rgba(217,119,87,0.1)',
        borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: '0.5px solid rgba(217,119,87,0.3)'
      }}>
        <MessageSquare size={24} style={{ color: 'var(--brand)' }} />
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 17, fontWeight: 500, marginBottom: 6 }}>Start a chat</div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 360, lineHeight: 1.6 }}>
          General chat is separate from projects. Use it for normal AI conversation, memory, explanations, and planning.
        </div>
      </div>
      <button
        onClick={onNewChat}
        style={{
          display: 'flex', alignItems: 'center', gap: 7, padding: '8px 20px',
          background: 'var(--brand-dark)', border: 'none', borderRadius: 8,
          color: 'white', fontSize: 13, fontWeight: 500, cursor: 'pointer'
        }}
      >
        <Plus size={15} /> New chat
      </button>
    </div>
  )
}

function ProjectEmptyState() {
  return (
    <div style={{
      flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexDirection: 'column', gap: 16
    }}>
      <div style={{
        width: 56, height: 56, background: 'rgba(217,119,87,0.1)',
        borderRadius: 16, display: 'flex', alignItems: 'center', justifyContent: 'center',
        border: '0.5px solid rgba(217,119,87,0.3)'
      }}>
        <Zap size={24} style={{ color: 'var(--brand)' }} />
      </div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: 17, fontWeight: 500, marginBottom: 6 }}>CrewDev Projects</div>
        <div style={{ fontSize: 13, color: 'var(--text-muted)', maxWidth: 340, lineHeight: 1.6 }}>
          Select a project or create one from the Projects section. Project chat uses code agents, files, memory, and indexing.
        </div>
      </div>
    </div>
  )
}

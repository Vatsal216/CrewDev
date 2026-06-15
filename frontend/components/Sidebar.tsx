'use client'
import { useEffect, useRef, useState } from 'react'
import { FolderOpen, MessageSquare, Plus, Settings, Zap, RefreshCw, Trash2, Pin, LayoutGrid, Code2 } from 'lucide-react'
import { useStore, Project, GeneralChat, CodeSession } from '@/lib/store'
import { api } from '@/lib/api'
import SettingsModal from '@/components/SettingsModal'

interface SidebarProps {
  onSelectProject: (project: Project) => void
  onSelectChat: (chat: GeneralChat) => void
  onNewChat: () => void
  onNewCode: () => void
  onSelectCode: (session: CodeSession) => void
}

function chatGroupLabel(createdAt: string) {
  const d = new Date(createdAt)
  const now = new Date()
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const startYesterday = startToday - 24 * 60 * 60 * 1000
  const time = new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime()
  if (time >= startToday) return 'TODAY'
  if (time >= startYesterday) return 'YESTERDAY'
  if (time >= startToday - 7 * 24 * 60 * 60 * 1000) return 'PREVIOUS 7 DAYS'
  return 'OLDER'
}

function groupChats(chats: GeneralChat[]) {
  const visible = chats.filter(c => !c.archived)
  const pinned = visible.filter(c => c.pinned)
  const normal = visible.filter(c => !c.pinned)
  const groups: Array<{ label: string; chats: GeneralChat[] }> = []
  if (pinned.length) groups.push({ label: 'PINNED', chats: pinned })
  for (const label of ['TODAY', 'YESTERDAY', 'PREVIOUS 7 DAYS', 'OLDER']) {
    const picked = normal.filter(c => chatGroupLabel(c.updated_at || c.created_at) === label)
    if (picked.length) groups.push({ label, chats: picked })
  }
  return groups
}

export default function Sidebar({ onSelectProject, onSelectChat, onNewChat, onNewCode, onSelectCode }: SidebarProps) {
  const {
    projects, setProjects, activeProjectId, addProject, updateProject,
    indexingProjectId, setIndexingProject, activeMode,
    generalChats, setGeneralChats, activeChatId, updateGeneralChat, removeGeneralChat,
    coworkSessions, setCoworkSessions, activeCoworkId, addCoworkSession, setActiveCowork, removeCoworkSession,
    codeSessions, setCodeSessions, activeCodeId, removeCodeSession,
    setErrorMessage,
  } = useStore()
  const [creating, setCreating] = useState(false)
  const [newName, setNewName] = useState('')
  const [search, setSearch] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    api.projects.list().then(setProjects).catch((e: any) => setErrorMessage(`Failed to load projects: ${e.message}`))
    api.chats.list().then(setGeneralChats).catch(() => {})
    api.cowork.list().then(setCoworkSessions).catch(() => {})
    api.code.list().then(setCodeSessions).catch(() => {})
  }, [setProjects, setGeneralChats, setCoworkSessions, setCodeSessions, setErrorMessage])

  useEffect(() => {
    if (creating) setTimeout(() => inputRef.current?.focus(), 50)
  }, [creating])

  async function createProject() {
    if (!newName.trim()) return
    setCreateError(null)
    try {
      const p = await api.projects.create(newName.trim())
      addProject(p)
      setNewName('')
      setCreating(false)
      onSelectProject(p)
    } catch (e: any) {
      setCreateError(e?.message || 'Failed to create project')
    }
  }

  async function deleteChat(e: React.MouseEvent, chatId: string) {
    e.stopPropagation()
    try {
      await api.chats.delete(chatId)
      removeGeneralChat(chatId)
    } catch {}
  }

  async function deleteCowork(e: React.MouseEvent, sessionId: string) {
    e.stopPropagation()
    try {
      await api.cowork.delete(sessionId)
      removeCoworkSession(sessionId)
    } catch (err: any) {
      setErrorMessage(`Failed to delete workspace: ${err?.message || err}`)
    }
  }

  async function deleteCode(e: React.MouseEvent, sessionId: string) {
    e.stopPropagation()
    try {
      await api.code.delete(sessionId)
      removeCodeSession(sessionId)
    } catch (err: any) {
      setErrorMessage(`Failed to delete Code workspace: ${err?.message || err}`)
    }
  }

  async function togglePinChat(e: React.MouseEvent, chat: GeneralChat) {
    e.stopPropagation()
    try {
      const updated = await api.chats.update(chat.id, { pinned: !chat.pinned })
      updateGeneralChat(chat.id, updated)
    } catch {}
  }

  async function indexProject(e: React.MouseEvent, projectId: string) {
    e.stopPropagation()
    setIndexingProject(projectId)
    try {
      await api.projects.index(projectId)
      updateProject(projectId, { index_status: 'indexing' })
      const poll = setInterval(async () => {
        const p = await api.projects.get(projectId)
        if (p.index_status === 'done' || p.index_status?.startsWith('error')) {
          updateProject(projectId, { indexed: p.indexed, index_status: p.index_status })
          setIndexingProject(null)
          clearInterval(poll)
        }
      }, 2000)
    } catch {
      setIndexingProject(null)
    }
  }

  const filteredChats = generalChats.filter(c => c.title.toLowerCase().includes(search.toLowerCase()))
  const chatGroups = groupChats(filteredChats)

  return (
    <>
    <aside style={{
      width: 250, minWidth: 250, background: 'var(--bg-secondary)',
      borderRight: '0.5px solid var(--border)', display: 'flex',
      flexDirection: 'column', height: '100%'
    }}>
      <div style={{ padding: '14px 14px 10px', borderBottom: '0.5px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <div style={{
            width: 28, height: 28, background: 'var(--brand-dark)', borderRadius: 8,
            display: 'flex', alignItems: 'center', justifyContent: 'center'
          }}>
            <Zap size={14} color="white" />
          </div>
          <span style={{ fontWeight: 500, fontSize: 14, color: 'var(--text-primary)' }}>CrewDev</span>
        </div>
        <button
          onClick={onNewChat}
          style={{
            width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            fontSize: 12, padding: '7px 10px', borderRadius: 7,
            border: '0.5px solid var(--border-strong)', background: activeMode === 'chat' ? 'var(--bg-hover)' : 'transparent',
            color: 'var(--text-secondary)', cursor: 'pointer', marginBottom: 8
          }}
        >
          <Plus size={13} /> New chat
        </button>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search chats"
          style={{
            width: '100%', fontSize: 12, padding: '6px 9px', borderRadius: 7,
            border: '0.5px solid var(--border)', background: 'var(--bg-tertiary)',
            color: 'var(--text-primary)', outline: 'none'
          }}
        />
      </div>

      <div style={{ flex: 1, overflowY: 'auto', paddingTop: 6 }}>
        <div style={{ padding: '6px 14px 4px', fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
          CHAT
        </div>

        {chatGroups.length === 0 && (
          <div style={{ padding: '8px 14px 12px', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
            No chats yet.
          </div>
        )}

        {chatGroups.map(group => (
          <div key={group.label}>
            <div style={{ padding: '8px 14px 4px', fontSize: 10, color: 'var(--text-muted)', letterSpacing: 0.5, textTransform: 'uppercase' }}>
              {group.label}
            </div>
            {group.chats.map(chat => (
              <div
                key={chat.id}
                onClick={() => onSelectChat(chat)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px 7px 14px',
                  cursor: 'pointer', fontSize: 12,
                  color: activeChatId === chat.id && activeMode === 'chat' ? 'var(--text-primary)' : 'var(--text-secondary)',
                  background: activeChatId === chat.id && activeMode === 'chat' ? 'rgba(217,119,87,0.14)' : 'transparent',
                  borderLeft: activeChatId === chat.id && activeMode === 'chat' ? '2px solid var(--brand)' : '2px solid transparent',
                }}
              >
                <MessageSquare size={13} style={{ flexShrink: 0 }} />
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {chat.title || 'New chat'}
                </span>
                <button
                  onClick={(e) => togglePinChat(e, chat)}
                  title={chat.pinned ? 'Unpin' : 'Pin'}
                  style={{ background: 'none', border: 'none', color: chat.pinned ? 'var(--brand-light)' : 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
                >
                  <Pin size={11} />
                </button>
                <button
                  onClick={(e) => deleteChat(e, chat.id)}
                  title="Delete chat"
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
                >
                  <Trash2 size={11} />
                </button>
              </div>
            ))}
          </div>
        ))}

        <div style={{
          margin: '10px 14px 6px', borderTop: '0.5px solid var(--border)', paddingTop: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8
        }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: 5 }}>
            <Code2 size={10} /> CODE
          </div>
          <button
            onClick={onNewCode}
            title="New Code workspace"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
          >
            <Plus size={13} />
          </button>
        </div>

        {codeSessions.length === 0 && (
          <div style={{ padding: '4px 14px 8px', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
            No Code workspaces yet.
          </div>
        )}

        {codeSessions.map(s => (
          <div
            key={s.id}
            onClick={() => onSelectCode(s)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px 7px 14px',
              cursor: 'pointer', fontSize: 12,
              color: activeCodeId === s.id && activeMode === 'code' ? 'var(--text-primary)' : 'var(--text-secondary)',
              background: activeCodeId === s.id && activeMode === 'code' ? 'rgba(217,119,87,0.14)' : 'transparent',
              borderLeft: activeCodeId === s.id && activeMode === 'code' ? '2px solid var(--brand)' : '2px solid transparent',
            }}
          >
            <Code2 size={13} style={{ flexShrink: 0 }} />
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {s.title || 'Code workspace'}
            </span>
            <button
              onClick={(e) => deleteCode(e, s.id)}
              title="Delete Code workspace"
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
            >
              <Trash2 size={11} />
            </button>
          </div>
        ))}

        <div style={{
          margin: '10px 14px 6px', borderTop: '0.5px solid var(--border)', paddingTop: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8
        }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.05em', display: 'flex', alignItems: 'center', gap: 5 }}>
            <LayoutGrid size={10} /> COWORK
          </div>
          <button
            onClick={async () => {
              try {
                const s = await api.cowork.create()
                addCoworkSession(s)
                setActiveCowork(s.id)
              } catch {}
            }}
            title="New workspace"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
          >
            <Plus size={13} />
          </button>
        </div>

        {coworkSessions.length === 0 && (
          <div style={{ padding: '4px 14px 8px', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
            No workspaces yet.
          </div>
        )}

        {coworkSessions.map(s => (
          <div
            key={s.id}
            onClick={() => setActiveCowork(s.id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px 7px 14px',
              cursor: 'pointer', fontSize: 12,
              color: activeCoworkId === s.id && activeMode === 'cowork' ? 'var(--text-primary)' : 'var(--text-secondary)',
              background: activeCoworkId === s.id && activeMode === 'cowork' ? 'rgba(217,119,87,0.14)' : 'transparent',
              borderLeft: activeCoworkId === s.id && activeMode === 'cowork' ? '2px solid var(--brand)' : '2px solid transparent',
            }}
          >
            <LayoutGrid size={13} style={{ flexShrink: 0 }} />
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {s.title || 'New workspace'}
            </span>
            <button
              onClick={(e) => deleteCowork(e, s.id)}
              title="Delete workspace"
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
            >
              <Trash2 size={11} />
            </button>
          </div>
        ))}

        <div style={{
          margin: '10px 14px 6px', borderTop: '0.5px solid var(--border)', paddingTop: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8
        }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', letterSpacing: '0.05em' }}>PROJECTS</div>
          <button
            onClick={() => setCreating(true)}
            title="New project"
            style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
          >
            <Plus size={13} />
          </button>
        </div>

        {creating && (
          <div style={{ margin: '0 14px 8px' }}>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                ref={inputRef}
                value={newName}
                onChange={e => setNewName(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') createProject(); if (e.key === 'Escape') { setCreating(false); setCreateError(null) } }}
                placeholder="Project name"
                style={{
                  flex: 1, fontSize: 12, padding: '4px 8px', borderRadius: 5,
                  border: '0.5px solid var(--brand)', background: 'var(--bg-tertiary)',
                  color: 'var(--text-primary)', outline: 'none', minWidth: 0
                }}
              />
              <button onClick={createProject} style={{
                padding: '4px 8px', borderRadius: 5, background: 'var(--brand-dark)',
                border: 'none', color: 'white', fontSize: 11, cursor: 'pointer'
              }}>Add</button>
            </div>
            {createError && (
              <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 4 }}>{createError}</div>
            )}
          </div>
        )}

        {projects.map(p => (
          <div
            key={p.id}
            onClick={() => onSelectProject(p)}
            style={{
              display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px 7px 14px',
              cursor: 'pointer', fontSize: 12,
              color: activeProjectId === p.id && activeMode === 'project' ? 'var(--text-primary)' : 'var(--text-secondary)',
              background: activeProjectId === p.id && activeMode === 'project' ? 'rgba(217,119,87,0.14)' : 'transparent',
              borderLeft: activeProjectId === p.id && activeMode === 'project' ? '2px solid var(--brand)' : '2px solid transparent',
            }}
          >
            <FolderOpen size={13} style={{ flexShrink: 0 }} />
            <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {p.name}
            </span>
            <div style={{
              width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
              background: p.indexed ? 'var(--green)' : p.index_status === 'indexing' ? 'var(--amber)' : 'var(--text-muted)'
            }} />
            {!p.indexed && indexingProjectId !== p.id && (
              <button
                onClick={e => indexProject(e, p.id)}
                title="Index project"
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
              >
                <RefreshCw size={11} />
              </button>
            )}
            {indexingProjectId === p.id && (
              <RefreshCw size={11} style={{ color: 'var(--amber)', animation: 'spin 1s linear infinite' }} />
            )}
          </div>
        ))}
      </div>

      <div style={{ padding: '10px 14px', borderTop: '0.5px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
          <div style={{
            width: 26, height: 26, borderRadius: '50%', background: 'rgba(217,119,87,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, fontWeight: 500, color: 'var(--brand-light)'
          }}>VA</div>
          <span style={{ flex: 1 }}>Vatsal</span>
          <button onClick={() => setShowSettings(true)} title="Settings"
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 4 }}>
            <Settings size={15} />
          </button>
        </div>
      </div>
    </aside>
    {showSettings && <SettingsModal onClose={() => setShowSettings(false)} />}
    </>
  )
}

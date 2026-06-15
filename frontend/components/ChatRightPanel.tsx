'use client'
import { useEffect, useState } from 'react'
import { Brain, FileText, Trash2 } from 'lucide-react'
import { api } from '@/lib/api'
import { useStore, ChatMemory } from '@/lib/store'

export default function ChatRightPanel() {
  const [tab, setTab] = useState<'memory' | 'artifacts'>('memory')
  const { chatMemories, setChatMemories } = useStore()

  useEffect(() => {
    api.chats.memories().then(setChatMemories).catch(() => {})
  }, [setChatMemories])

  async function deleteMemory(memoryId: string) {
    await api.chats.deleteMemory(memoryId)
    setChatMemories(chatMemories.filter(m => m.id !== memoryId))
  }

  const tabs = [
    { key: 'memory', label: 'Memory', icon: <Brain size={12} /> },
    { key: 'artifacts', label: 'Artifacts', icon: <FileText size={12} /> },
  ] as const

  return (
    <div style={{
      width: 240, minWidth: 240, borderLeft: '0.5px solid var(--border)',
      background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column'
    }}>
      <div style={{ display: 'flex', borderBottom: '0.5px solid var(--border)' }}>
        {tabs.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              padding: '9px 0', fontSize: 11, background: 'none', border: 'none', cursor: 'pointer',
              color: tab === t.key ? 'var(--brand)' : 'var(--text-muted)',
              borderBottom: tab === t.key ? '2px solid var(--brand)' : '2px solid transparent',
              fontWeight: tab === t.key ? 500 : 400,
            }}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {tab === 'memory' ? (
        <MemoryList memories={chatMemories} onDelete={deleteMemory} />
      ) : (
        <ArtifactsPlaceholder />
      )}
    </div>
  )
}

function MemoryList({ memories, onDelete }: { memories: ChatMemory[]; onDelete: (id: string) => void }) {
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 10 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10, lineHeight: 1.5 }}>
        General chat memory. This is separate from project memory and can be deleted anytime.
      </div>
      {memories.length === 0 ? (
        <div style={{
          padding: 12, border: '0.5px solid var(--border)', borderRadius: 8,
          background: 'var(--bg-tertiary)', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5
        }}>
          No memories saved yet. Useful stable preferences from chat will appear here.
        </div>
      ) : memories.map(memory => (
        <div key={memory.id} style={{
          marginBottom: 8, padding: '8px 10px', borderRadius: 8,
          border: '0.5px solid var(--border)', background: 'var(--bg-tertiary)'
        }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
            <div style={{ flex: 1, fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              {memory.content}
            </div>
            <button
              title="Delete memory"
              onClick={() => onDelete(memory.id)}
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: 0 }}
            >
              <Trash2 size={12} />
            </button>
          </div>
          <div style={{ marginTop: 6, fontSize: 10, color: 'var(--text-muted)' }}>{memory.memory_type}</div>
        </div>
      ))}
    </div>
  )
}

function ArtifactsPlaceholder() {
  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: 10 }}>
      <div style={{
        padding: 12, border: '0.5px solid var(--border)', borderRadius: 8,
        background: 'var(--bg-tertiary)', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5
      }}>
        Artifact panel is ready for Claude-style documents/code outputs. The current build stores normal messages and memory first.
      </div>
    </div>
  )
}

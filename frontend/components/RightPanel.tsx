'use client'
import { useState, useEffect } from 'react'
import { Upload, RefreshCw, FolderOpen, Brain } from 'lucide-react'
import { useStore } from '@/lib/store'
import { api } from '@/lib/api'
import FileExplorer from './FileExplorer'

interface RightPanelProps {
  projectId: string
}

export default function RightPanel({ projectId }: RightPanelProps) {
  const [tab, setTab] = useState<'files' | 'memory'>('files')
  const { fileTree, setFileTree, projects, updateProject } = useStore()
  const project = projects.find(p => p.id === projectId)

  useEffect(() => {
    api.projects.files(projectId).then(r => setFileTree(r.tree)).catch(() => {})
  }, [projectId])

  async function upload(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files?.length) return
    await api.projects.upload(projectId, e.target.files)
    const r = await api.projects.files(projectId)
    setFileTree(r.tree)
  }

  async function index() {
    await api.projects.index(projectId)
    updateProject(projectId, { index_status: 'indexing' })
    // Poll
    const poll = setInterval(async () => {
      const p = await api.projects.get(projectId)
      updateProject(projectId, { indexed: p.indexed, index_status: p.index_status })
      if (p.index_status === 'done' || p.index_status?.startsWith('error')) clearInterval(poll)
    }, 2000)
  }

  const TABS = [
    { key: 'files', label: 'Files', icon: <FolderOpen size={12} /> },
    { key: 'memory', label: 'Memory', icon: <Brain size={12} /> },
  ]

  return (
    <div style={{
      width: 220, minWidth: 220, borderLeft: '0.5px solid var(--border)',
      background: 'var(--bg-secondary)', display: 'flex', flexDirection: 'column'
    }}>
      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '0.5px solid var(--border)' }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key as any)}
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

      {/* Files tab */}
      {tab === 'files' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {/* Actions */}
          <div style={{ padding: '8px 10px', display: 'flex', gap: 6, borderBottom: '0.5px solid var(--border)' }}>
            <label style={{
              flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
              fontSize: 11, padding: '4px 0', borderRadius: 5, cursor: 'pointer',
              border: '0.5px solid var(--border)', color: 'var(--text-secondary)', background: 'none'
            }}>
              <Upload size={11} /> Upload
              <input type="file" multiple style={{ display: 'none' }} onChange={upload} />
            </label>
            <button
              onClick={index}
              title={project?.indexed ? 'Re-index' : 'Index project for semantic search'}
              style={{
                flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
                fontSize: 11, padding: '4px 0', borderRadius: 5, cursor: 'pointer',
                border: `0.5px solid ${project?.indexed ? 'var(--green)' : 'var(--border)'}`,
                color: project?.indexed ? 'var(--green)' : 'var(--text-secondary)', background: 'none'
              }}
            >
              <RefreshCw size={11} />
              {project?.index_status === 'indexing' ? 'Indexing…' : project?.indexed ? 'Indexed' : 'Index'}
            </button>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', paddingTop: 4 }}>
            <FileExplorer tree={fileTree} />
          </div>
        </div>
      )}

      {/* Memory tab */}
      {tab === 'memory' && (
        <div style={{ flex: 1, overflowY: 'auto', padding: '10px' }}>
          <MemoryPanel projectId={projectId} />
        </div>
      )}
    </div>
  )
}

function MemoryPanel({ projectId }: { projectId: string }) {
  const [harness, setHarness] = useState<any>(null)

  useEffect(() => {
    api.projects.get(projectId).then(setHarness).catch(() => {})
  }, [projectId])

  return (
    <div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 10 }}>
        Project harness state
      </div>
      {[
        { label: 'Goals', value: 'Loaded from project harness' },
        { label: 'Architecture', value: 'Multi-agent CrewAI orchestration' },
        { label: 'Tech stack', value: 'CrewAI · FastAPI · ChromaDB · Voyage' },
        { label: 'Active tasks', value: 'Streamed from last session' },
      ].map(item => (
        <div key={item.label} style={{
          marginBottom: 8, padding: '7px 10px', borderRadius: 6,
          border: '0.5px solid var(--border)', background: 'var(--bg-tertiary)'
        }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 3 }}>{item.label}</div>
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{item.value}</div>
        </div>
      ))}
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6, textAlign: 'center' }}>
        Memory auto-updates after each conversation
      </div>
    </div>
  )
}

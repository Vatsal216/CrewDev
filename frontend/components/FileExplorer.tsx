'use client'
import { useState } from 'react'
import { Folder, FolderOpen, FileCode, File, ChevronRight, ChevronDown } from 'lucide-react'
import { FileNode } from '@/lib/store'

const EXT_COLORS: Record<string, string> = {
  '.py': '#3B8BD4',
  '.ts': '#3B8BD4',
  '.tsx': '#1D9E75',
  '.js': '#BA7517',
  '.jsx': '#BA7517',
  '.json': '#D85A30',
  '.md': '#D97757',
  '.yml': '#993556',
  '.yaml': '#993556',
  '.css': '#D4537E',
  '.html': '#D85A30',
}

function FileItem({ node, depth = 0 }: { node: FileNode; depth?: number }) {
  const [expanded, setExpanded] = useState(depth < 2)
  const indent = depth * 14 + 10

  if (node.type === 'dir') {
    return (
      <div>
        <div
          onClick={() => setExpanded(!expanded)}
          style={{
            display: 'flex', alignItems: 'center', gap: 5, padding: `4px ${indent}px 4px 10px`,
            cursor: 'pointer', fontSize: 12, color: 'var(--text-secondary)',
            paddingLeft: indent,
          }}
          onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-primary)')}
          onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-secondary)')}
        >
          <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>
            {expanded ? <ChevronDown size={11} /> : <ChevronRight size={11} />}
          </span>
          {expanded ? <FolderOpen size={13} style={{ color: '#BA7517' }} /> : <Folder size={13} style={{ color: '#BA7517' }} />}
          <span>{node.name}</span>
        </div>
        {expanded && node.children?.map(child => (
          <FileItem key={child.path} node={child} depth={depth + 1} />
        ))}
      </div>
    )
  }

  const color = EXT_COLORS[node.extension || ''] || 'var(--text-muted)'

  return (
    <div
      style={{
        display: 'flex', alignItems: 'center', gap: 5, padding: '3px 10px',
        paddingLeft: indent + 16, cursor: 'pointer', fontSize: 11, color: 'var(--text-muted)'
      }}
      onMouseEnter={e => (e.currentTarget.style.color = 'var(--text-secondary)')}
      onMouseLeave={e => (e.currentTarget.style.color = 'var(--text-muted)')}
    >
      <FileCode size={12} style={{ color, flexShrink: 0 }} />
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{node.name}</span>
      {node.size !== undefined && (
        <span style={{ marginLeft: 'auto', flexShrink: 0, fontSize: 10, color: 'var(--text-muted)' }}>
          {node.size < 1024 ? `${node.size}b` : `${(node.size / 1024).toFixed(1)}k`}
        </span>
      )}
    </div>
  )
}

interface FileExplorerProps {
  tree: FileNode[]
}

export default function FileExplorer({ tree }: FileExplorerProps) {
  if (!tree.length) {
    return (
      <div style={{ padding: '16px 14px', fontSize: 12, color: 'var(--text-muted)', textAlign: 'center' }}>
        No files yet.<br />Upload files or create a project.
      </div>
    )
  }
  return (
    <div>
      {tree.map(node => <FileItem key={node.path} node={node} />)}
    </div>
  )
}

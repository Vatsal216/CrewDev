'use client'
import { useState } from 'react'
import { Play, Loader2 } from 'lucide-react'
import { api } from '@/lib/api'

interface ExecResult {
  run_id: string; stdout: string; stderr: string; exit_code: number
  timed_out: boolean; artifacts: { name: string; is_image: boolean }[]
}

export default function CodeBlock({ className, children, ...props }: any) {
  const match = /language-(\w+)/.exec(className || '')
  const lang = match?.[1]
  const code = String(children ?? '').replace(/\n$/, '')
  const [result, setResult] = useState<ExecResult | null>(null)
  const [running, setRunning] = useState(false)

  // inline code (no language) → render plainly
  if (!lang) {
    return <code className={className} {...props}>{children}</code>
  }

  const runnable = lang === 'python' || lang === 'py'

  async function run() {
    setRunning(true)
    try {
      setResult(await api.exec.run(code))
    } catch (e: any) {
      setResult({ run_id: '', stdout: '', stderr: e.message || 'Run failed', exit_code: 1, timed_out: false, artifacts: [] })
    }
    setRunning(false)
  }

  return (
    <div>
      <div style={{ position: 'relative' }}>
        <pre><code className={className}>{children}</code></pre>
        {runnable && (
          <button onClick={run} disabled={running} title="Run"
            style={{ position: 'absolute', top: 8, right: 8, display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, padding: '3px 8px', borderRadius: 6, border: '0.5px solid var(--border)', background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', cursor: 'pointer' }}>
            {running ? <Loader2 size={12} style={{ animation: 'spin 1s linear infinite' }} /> : <Play size={12} />} Run
          </button>
        )}
      </div>
      {result && (
        <div style={{ marginTop: 6, border: '0.5px solid var(--border)', borderRadius: 8, padding: 10, fontSize: 12, background: 'var(--bg-secondary)' }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>
            {result.timed_out ? 'TIMED OUT' : `EXIT ${result.exit_code}`}
          </div>
          {result.stdout && <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{result.stdout}</pre>}
          {result.stderr && <pre style={{ whiteSpace: 'pre-wrap', margin: 0, color: 'var(--red)' }}>{result.stderr}</pre>}
          {result.artifacts.map(a => a.is_image
            ? <img key={a.name} src={api.exec.artifactUrl(result.run_id, a.name)} alt={a.name} style={{ maxWidth: '100%', marginTop: 6, borderRadius: 6 }} />
            : <a key={a.name} href={api.exec.artifactUrl(result.run_id, a.name)} target="_blank" rel="noreferrer" style={{ display: 'block', marginTop: 4, color: 'var(--brand-light)' }}>{a.name}</a>)}
        </div>
      )}
    </div>
  )
}

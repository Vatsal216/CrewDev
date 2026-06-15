'use client'
import { useEffect, useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { useStore } from '@/lib/store'
import { api } from '@/lib/api'

interface ModelPickerProps {
  providerId: string | null
  model: string | null
  onChange: (providerId: string, model: string) => void
}

export default function ModelPicker({ providerId, model, onChange }: ModelPickerProps) {
  const { providers, setProviders } = useStore()
  const [open, setOpen] = useState(false)
  const [modelsByProvider, setModelsByProvider] = useState<Record<string, string[]>>({})

  useEffect(() => {
    if (providers.length === 0) {
      api.providers.list().then(setProviders).catch(() => {})
    }
  }, [providers.length, setProviders])

  useEffect(() => {
    if (!open) return
    const enabled = providers.filter(p => p.enabled)
    enabled.forEach(p => {
      if (modelsByProvider[p.id]) return
      api.providers.models(p.id)
        .then(r => setModelsByProvider(prev => ({ ...prev, [p.id]: r.models })))
        .catch(() => setModelsByProvider(prev => ({ ...prev, [p.id]: [] })))
    })
  }, [open, providers, modelsByProvider])

  const current = providers.find(p => p.id === providerId)
  const label = model ? `${current?.label ?? 'Model'}: ${model}` : 'Select model'

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 11,
          color: 'var(--text-secondary)', background: 'var(--bg-tertiary)',
          padding: '3px 10px', borderRadius: 99, border: '0.5px solid var(--border)', cursor: 'pointer',
        }}
      >
        {label} <ChevronDown size={12} />
      </button>
      {open && (
        <div style={{
          position: 'absolute', top: '110%', right: 0, zIndex: 50, minWidth: 220,
          background: 'var(--bg-secondary)', border: '0.5px solid var(--border-strong)',
          borderRadius: 10, padding: 6, maxHeight: 320, overflowY: 'auto',
          boxShadow: '0 8px 30px rgba(0,0,0,0.25)',
        }}>
          {providers.filter(p => p.enabled).length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', padding: 8 }}>
              No providers. Add one in Settings.
            </div>
          )}
          {providers.filter(p => p.enabled).map(p => (
            <div key={p.id} style={{ marginBottom: 4 }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', padding: '4px 8px', textTransform: 'uppercase' }}>
                {p.label}
              </div>
              {(modelsByProvider[p.id] ?? []).map(m => (
                <button
                  key={`${p.id}:${m}`}
                  onClick={() => { onChange(p.id, m); setOpen(false) }}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left', fontSize: 12,
                    padding: '6px 8px', borderRadius: 6, border: 'none', cursor: 'pointer',
                    background: (p.id === providerId && m === model) ? 'var(--bg-hover)' : 'transparent',
                    color: 'var(--text-primary)',
                  }}
                >
                  {m}
                </button>
              ))}
              {(modelsByProvider[p.id]?.length ?? 0) === 0 && (
                <div style={{ fontSize: 11, color: 'var(--text-muted)', padding: '2px 8px' }}>
                  {p.provider === 'ollama' ? 'No models (is Ollama running?)' : 'No models listed'}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

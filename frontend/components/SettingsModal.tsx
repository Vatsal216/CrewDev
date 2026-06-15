'use client'
import { useEffect, useState } from 'react'
import { X, Plus, Trash2, CheckCircle2, XCircle } from 'lucide-react'
import { useStore, Provider, Skill } from '@/lib/store'
import { api } from '@/lib/api'
import { getSttMode, setSttMode, SttMode } from '@/lib/voice'

type ProviderField = {
  key: string
  label: string
  placeholder?: string
  helper?: string
  secret?: boolean
}

const PROVIDER_FIELDS: Record<string, ProviderField[]> = {
  anthropic: [
    { key: 'api_key', label: 'API Key', placeholder: 'sk-ant-...', secret: true },
  ],
  openai: [
    { key: 'api_key', label: 'API Key', placeholder: 'sk-...', secret: true },
    { key: 'api_base', label: 'Base URL', placeholder: 'Optional, e.g. https://api.openai.com/v1' },
    { key: 'organization', label: 'Organization', placeholder: 'Optional' },
  ],
  azure: [
    { key: 'api_key', label: 'API Key', placeholder: 'Azure OpenAI key', secret: true },
    { key: 'api_base', label: 'Endpoint', placeholder: 'https://<resource>.openai.azure.com' },
    { key: 'api_version', label: 'API Version', placeholder: '2024-02-15-preview' },
  ],
  ollama: [
    {
      key: 'api_base',
      label: 'Base URL',
      placeholder: 'Local: http://localhost:11434  |  Cloud: https://ollama.com',
      helper: 'Use http://localhost:11434 for local Ollama, or https://ollama.com for Ollama Cloud.',
    },
    {
      key: 'api_key',
      label: 'API Key',
      placeholder: 'Required for Ollama Cloud; leave blank for local Ollama',
      helper: 'Only required when Base URL is https://ollama.com or https://ollama.com/api.',
      secret: true,
    },
  ],
}

export default function SettingsModal({ onClose }: { onClose: () => void }) {
  const { providers, setProviders, defaultModel, setDefaultModel, skills, setSkills } = useStore()
  const [adding, setAdding] = useState(false)
  const [newProvider, setNewProvider] = useState('openai')
  const [newLabel, setNewLabel] = useState('')
  const [newConfig, setNewConfig] = useState<Record<string, string>>({})
  const [testResult, setTestResult] = useState<Record<string, { ok: boolean; message: string }>>({})
  const [sttMode, setMode] = useState<SttMode>('browser')

  // Skills form state
  const [addingSkill, setAddingSkill] = useState(false)
  const [newSkillName, setNewSkillName] = useState('')
  const [newSkillDesc, setNewSkillDesc] = useState('')
  const [newSkillInstr, setNewSkillInstr] = useState('')

  useEffect(() => {
    api.providers.list().then(setProviders).catch(() => {})
    api.settings.getDefaultModel().then(r => setDefaultModel(r.value)).catch(() => {})
    api.skills.list().then(setSkills).catch(() => {})
    setMode(getSttMode())
  }, [setProviders, setDefaultModel, setSkills])

  async function addProvider() {
    if (!newLabel.trim()) return
    try {
      await api.providers.create({ provider: newProvider, label: newLabel.trim(), config: newConfig, is_default: providers.length === 0 })
      setProviders(await api.providers.list())
      setAdding(false); setNewLabel(''); setNewConfig({})
    } catch {}
  }

  async function removeProvider(id: string) {
    try { await api.providers.delete(id); setProviders(await api.providers.list()) } catch {}
  }

  async function toggleEnabled(p: Provider) {
    try { await api.providers.update(p.id, { enabled: !p.enabled }); setProviders(await api.providers.list()) } catch {}
  }

  async function testProvider(id: string) {
    try {
      const r = await api.providers.test(id)
      setTestResult(prev => ({ ...prev, [id]: { ok: r.ok, message: r.message } }))
    } catch (e: any) {
      setTestResult(prev => ({ ...prev, [id]: { ok: false, message: e.message } }))
    }
  }

  async function toggleSkill(s: Skill) {
    try { await api.skills.update(s.id, { enabled: !s.enabled }); setSkills(await api.skills.list()) } catch {}
  }

  async function deleteSkill(id: string) {
    try { await api.skills.delete(id); setSkills(await api.skills.list()) } catch {}
  }

  async function addSkill() {
    if (!newSkillName.trim()) return
    try {
      await api.skills.create({ name: newSkillName.trim(), description: newSkillDesc, instructions: newSkillInstr })
      setSkills(await api.skills.list())
      setAddingSkill(false); setNewSkillName(''); setNewSkillDesc(''); setNewSkillInstr('')
    } catch {}
  }

  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        width: 560, maxHeight: '80vh', overflowY: 'auto', background: 'var(--bg-primary)',
        border: '0.5px solid var(--border-strong)', borderRadius: 14, padding: 20,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 16 }}>
          <span style={{ fontSize: 15, fontWeight: 600 }}>Providers</span>
          <button onClick={onClose} style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, fontSize: 12, color: 'var(--text-secondary)' }}>
          <span>Voice input</span>
          {(['browser', 'server'] as SttMode[]).map(m => (
            <button key={m} onClick={() => { setSttMode(m); setMode(m) }}
              style={{ fontSize: 11, padding: '3px 10px', borderRadius: 99, cursor: 'pointer',
                border: '0.5px solid var(--border)',
                background: sttMode === m ? 'rgba(217,119,87,0.14)' : 'var(--bg-tertiary)',
                color: sttMode === m ? 'var(--text-primary)' : 'var(--text-secondary)' }}>
              {m === 'browser' ? 'Browser' : 'Server (Whisper)'}
            </button>
          ))}
        </div>

        {providers.map(p => (
          <div key={p.id} style={{
            border: '0.5px solid var(--border)', borderRadius: 10, padding: 12, marginBottom: 10,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 500 }}>{p.label}</span>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{p.provider}</span>
              {p.is_default && <span style={{ fontSize: 10, color: 'var(--brand-light)' }}>default</span>}
              <button onClick={() => toggleEnabled(p)} style={{
                marginLeft: 'auto', fontSize: 11, cursor: 'pointer', background: 'var(--bg-tertiary)',
                border: '0.5px solid var(--border)', borderRadius: 6, padding: '2px 8px', color: 'var(--text-secondary)',
              }}>
                {p.enabled ? 'Enabled' : 'Disabled'}
              </button>
              <button onClick={() => testProvider(p.id)} style={{ fontSize: 11, cursor: 'pointer', background: 'var(--bg-tertiary)', border: '0.5px solid var(--border)', borderRadius: 6, padding: '2px 8px', color: 'var(--text-secondary)' }}>
                Test
              </button>
              <button onClick={() => removeProvider(p.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                <Trash2 size={14} />
              </button>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 6 }}>
              {p.has_key ? `key ${p.key_masked}` : 'no key'}
            </div>
            {testResult[p.id] && (
              <div style={{ fontSize: 11, marginTop: 6, display: 'flex', alignItems: 'center', gap: 5, color: testResult[p.id].ok ? 'var(--green)' : 'var(--red)' }}>
                {testResult[p.id].ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
                {testResult[p.id].message}
              </div>
            )}
          </div>
        ))}

        {adding ? (
          <div style={{ border: '0.5px solid var(--border-strong)', borderRadius: 10, padding: 12, marginTop: 8 }}>
            <select value={newProvider} onChange={e => { setNewProvider(e.target.value); setNewConfig({}) }}
              style={{ fontSize: 12, padding: 6, borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '0.5px solid var(--border)', marginBottom: 8 }}>
              <option value="anthropic">Anthropic</option>
              <option value="openai">OpenAI</option>
              <option value="azure">Azure OpenAI</option>
              <option value="ollama">Ollama</option>
            </select>

            {newProvider === 'ollama' && (
              <div style={{
                fontSize: 11, color: 'var(--text-secondary)', background: 'var(--bg-tertiary)',
                border: '0.5px solid var(--border)', borderRadius: 8, padding: 10, marginBottom: 10, lineHeight: 1.45,
              }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>Ollama setup</div>
                <div>Local: Base URL <code>http://localhost:11434</code>, API Key blank.</div>
                <div>Cloud: Base URL <code>https://ollama.com</code>, API Key required.</div>
                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button type="button" onClick={() => setNewConfig(prev => ({ ...prev, api_base: 'http://localhost:11434', api_key: '' }))}
                    style={{ fontSize: 11, padding: '4px 8px', borderRadius: 6, border: '0.5px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                    Use local
                  </button>
                  <button type="button" onClick={() => setNewConfig(prev => ({ ...prev, api_base: 'https://ollama.com' }))}
                    style={{ fontSize: 11, padding: '4px 8px', borderRadius: 6, border: '0.5px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer' }}>
                    Use cloud
                  </button>
                </div>
              </div>
            )}

            <label style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>Label</label>
            <input placeholder="Display name, e.g. Ollama Cloud" value={newLabel} onChange={e => setNewLabel(e.target.value)}
              style={{ display: 'block', width: '100%', fontSize: 12, padding: 7, marginBottom: 10, borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '0.5px solid var(--border)' }} />

            {PROVIDER_FIELDS[newProvider].map(f => (
              <div key={f.key} style={{ marginBottom: 10 }}>
                <label style={{ display: 'block', fontSize: 11, color: 'var(--text-muted)', marginBottom: 4 }}>
                  {f.label}
                </label>
                <input placeholder={f.placeholder ?? f.label} type={f.secret ? 'password' : 'text'}
                  autoComplete={f.secret ? 'new-password' : 'off'}
                  value={newConfig[f.key] ?? ''} onChange={e => setNewConfig(prev => ({ ...prev, [f.key]: e.target.value }))}
                  style={{ display: 'block', width: '100%', fontSize: 12, padding: 7, borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '0.5px solid var(--border)' }} />
                {f.helper && (
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4, lineHeight: 1.35 }}>{f.helper}</div>
                )}
              </div>
            ))}
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={addProvider} style={{ fontSize: 12, padding: '6px 14px', borderRadius: 7, border: 'none', background: 'var(--brand-dark)', color: 'white', cursor: 'pointer' }}>Save</button>
              <button onClick={() => setAdding(false)} style={{ fontSize: 12, padding: '6px 14px', borderRadius: 7, border: '0.5px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer' }}>Cancel</button>
            </div>
          </div>
        ) : (
          <button onClick={() => setAdding(true)} style={{
            display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '8px 14px', marginTop: 8,
            borderRadius: 8, border: '0.5px solid var(--border)', background: 'var(--bg-tertiary)', color: 'var(--text-primary)', cursor: 'pointer',
          }}>
            <Plus size={14} /> Add provider
          </button>
        )}

        {/* ── Skills ── */}
        <div style={{ borderTop: '0.5px solid var(--border)', marginTop: 20, paddingTop: 16 }}>
          <span style={{ fontSize: 14, fontWeight: 600 }}>Skills</span>
        </div>

        {skills.map(s => (
          <div key={s.id} style={{
            border: '0.5px solid var(--border)', borderRadius: 10, padding: 12, marginBottom: 10, marginTop: 10,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 13, fontWeight: 500 }}>{s.name}</span>
              {s.description && (
                <span style={{ fontSize: 11, color: 'var(--text-muted)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{s.description}</span>
              )}
              <button onClick={() => toggleSkill(s)} style={{
                marginLeft: 'auto', fontSize: 11, cursor: 'pointer', background: 'var(--bg-tertiary)',
                border: '0.5px solid var(--border)', borderRadius: 6, padding: '2px 8px', color: 'var(--text-secondary)',
              }}>
                {s.enabled ? 'Enabled' : 'Disabled'}
              </button>
              <button onClick={() => deleteSkill(s.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}>
                <Trash2 size={14} />
              </button>
            </div>
          </div>
        ))}

        {addingSkill ? (
          <div style={{ border: '0.5px solid var(--border-strong)', borderRadius: 10, padding: 12, marginTop: 8 }}>
            <input placeholder="Skill name" value={newSkillName} onChange={e => setNewSkillName(e.target.value)}
              style={{ display: 'block', width: '100%', fontSize: 12, padding: 7, marginBottom: 8, borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '0.5px solid var(--border)' }} />
            <input placeholder="Description (when to activate)" value={newSkillDesc} onChange={e => setNewSkillDesc(e.target.value)}
              style={{ display: 'block', width: '100%', fontSize: 12, padding: 7, marginBottom: 8, borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '0.5px solid var(--border)' }} />
            <textarea placeholder="Instructions (injected into system prompt)" value={newSkillInstr} onChange={e => setNewSkillInstr(e.target.value)}
              style={{ display: 'block', width: '100%', fontSize: 12, padding: 7, marginBottom: 8, borderRadius: 6, background: 'var(--bg-secondary)', color: 'var(--text-primary)', border: '0.5px solid var(--border)', resize: 'vertical', minHeight: 72, fontFamily: 'inherit' }} />
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={addSkill} style={{ fontSize: 12, padding: '6px 14px', borderRadius: 7, border: 'none', background: 'var(--brand-dark)', color: 'white', cursor: 'pointer' }}>Save</button>
              <button onClick={() => setAddingSkill(false)} style={{ fontSize: 12, padding: '6px 14px', borderRadius: 7, border: '0.5px solid var(--border)', background: 'transparent', color: 'var(--text-secondary)', cursor: 'pointer' }}>Cancel</button>
            </div>
          </div>
        ) : (
          <button onClick={() => setAddingSkill(true)} style={{
            display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, padding: '8px 14px', marginTop: 8,
            borderRadius: 8, border: '0.5px solid var(--border)', background: 'var(--bg-tertiary)', color: 'var(--text-primary)', cursor: 'pointer',
          }}>
            <Plus size={14} /> Add skill
          </button>
        )}
      </div>
    </div>
  )
}

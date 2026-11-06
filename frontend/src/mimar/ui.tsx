import { isValidElement, ReactNode, useCallback, useEffect, useState } from 'react'
import clsx from 'clsx'
import { useMimar } from './state'

// data loading
export function useLoad<T = any>(fn: () => Promise<T>, deps: unknown[] = []) {
  const refreshKey = useMimar((s) => s.refreshKey)
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const reload = useCallback(() => {
    setLoading(true)
    fn().then((d) => { setData(d); setError(null) })
      .catch((e) => setError(e.message ?? String(e)))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, refreshKey])
  useEffect(() => { reload() }, [reload])
  return { data, error, loading, reload, setData }
}

/** Runs an action, shows its error inline, refreshes views on success. */
export function useAction() {
  const refresh = useMimar((s) => s.refresh)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<string | null>(null)
  const run = async <T,>(fn: () => Promise<T>, okMsg?: string): Promise<T | undefined> => {
    setBusy(true); setError(null); setDone(null)
    try {
      const r = await fn()
      if (okMsg) setDone(okMsg)
      refresh()
      return r
    } catch (e: any) {
      setError(e.message ?? String(e))
    } finally {
      setBusy(false)
    }
  }
  return { busy, error, done, run, setError }
}

// primitives
export function Button({ children, onClick, kind = 'secondary', disabled, busy, type = 'button', title }: {
  children: ReactNode; onClick?: () => void; kind?: 'primary' | 'secondary' | 'quiet' | 'danger'
  disabled?: boolean; busy?: boolean; type?: 'button' | 'submit'; title?: string
}) {
  return (
    <button type={type} title={title} onClick={onClick} disabled={disabled || busy}
      className={clsx('m-btn', `m-btn-${kind}`)}>
      {busy ? <span className="m-spinner" aria-hidden /> : null}{children}
    </button>
  )
}

export function Panel({ title, aside, children, className }: {
  title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string
}) {
  return (
    <section className={clsx('m-panel', className)}>
      {(title || aside) && (
        <header className="m-panel-head">
          {title && <h3>{title}</h3>}
          {aside && <div className="m-panel-aside">{aside}</div>}
        </header>
      )}
      {children}
    </section>
  )
}

export function Page({ title, lead, children, actions }: {
  title: string; lead?: ReactNode; children: ReactNode; actions?: ReactNode
}) {
  return (
    <div className="m-page">
      <div className="m-page-head">
        <div>
          <h2>{title}</h2>
          {lead && <p className="m-lead">{lead}</p>}
        </div>
        {actions && <div className="m-actions">{actions}</div>}
      </div>
      {children}
    </div>
  )
}

export const Note = ({ tone = 'info', children }: { tone?: 'info' | 'warn' | 'error' | 'ok'; children: ReactNode }) =>
  <div className={clsx('m-note', `m-note-${tone}`)} role={tone === 'error' ? 'alert' : undefined}>{children}</div>

export function Feedback({ a }: { a: { error: string | null; done: string | null } }) {
  if (a.error) return <Note tone="error">{a.error}</Note>
  if (a.done) return <Note tone="ok">{a.done}</Note>
  return null
}

export function Pill({ tone = 'plain', children }: { tone?: 'plain' | 'ok' | 'warn' | 'bad' | 'lock' | 'brand'; children: ReactNode }) {
  return <span className={clsx('m-pill', `m-pill-${tone}`)}>{children}</span>
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="m-stat">
      <div className="m-stat-value">{value ?? '—'}</div>
      <div className="m-stat-label">{label}</div>
      {hint && <div className="m-stat-hint">{hint}</div>}
    </div>
  )
}

export function Table({ cols, rows, empty = 'Nothing here yet.', dense }: {
  cols: { key: string; label: ReactNode; render?: (r: any) => ReactNode; num?: boolean; width?: string }[]
  rows: any[]; empty?: ReactNode; dense?: boolean
}) {
  if (!rows?.length) return <p className="m-empty">{empty}</p>
  return (
    <div className="m-table-wrap">
      <table className={clsx('m-table', dense && 'm-table-dense')}>
        <thead><tr>{cols.map((c) => <th key={c.key} style={{ width: c.width }} className={c.num ? 'num' : ''}>{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={r.id ?? r.code ?? r.key ?? i}>
              {cols.map((c) => <td key={c.key} className={c.num ? 'num' : ''}>{c.render ? c.render(r) : fmt(r[c.key])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return (
    <label className="m-field">
      <span className="m-field-label">{label}</span>
      {children}
      {hint && <span className="m-field-hint">{hint}</span>}
    </label>
  )
}

export function Select({ value, onChange, options, placeholder }: {
  value: string; onChange: (v: string) => void; options: { value: string; label: string }[]; placeholder?: string
}) {
  return (
    <select className="m-input" value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{placeholder ?? 'Seçin…'}</option>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  )
}

export function Hash({ value, n = 10 }: { value?: string | null; n?: number }) {
  if (!value) return <span className="m-muted">—</span>
  return <code className="m-hash" title={value}>{value.slice(0, n)}</code>
}

export function fmt(v: any, digits = 3): ReactNode {
  if (v === null || v === undefined || v === '') return <span className="m-muted">—</span>
  if (isValidElement(v)) return v
  if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString('tr-TR') : v.toFixed(digits)
  if (typeof v === 'boolean') return v ? 'yes' : 'no'
  if (Array.isArray(v)) return v.join(', ')
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

export const pct = (v: number | null | undefined, d = 1) =>
  v === null || v === undefined ? '—' : `${(v * 100).toFixed(d)}%`

export const ci = (c?: (number | null)[] | null, asPct = false, d = 3) =>
  !c || c[0] === null || c[0] === undefined ? '—'
    : asPct ? `${pct(c[0])} – ${pct(c[1])}` : `${Number(c[0]).toFixed(d)} – ${Number(c[1]).toFixed(d)}`

/** Small horizontal bar for proportions; the number stays the primary signal. */
export function Bar({ value, max = 1, tone = 'brand' }: { value: number | null | undefined; max?: number; tone?: 'brand' | 'ok' | 'muted' }) {
  const w = value === null || value === undefined ? 0 : Math.max(0, Math.min(1, value / max)) * 100
  return <span className="m-bar" aria-hidden><span className={`m-bar-fill m-bar-${tone}`} style={{ width: `${w}%` }} /></span>
}

export function Verdict({ ok, children }: { ok: boolean | null | undefined; children: ReactNode }) {
  return <div className={clsx('m-verdict', ok === true ? 'is-ok' : ok === false ? 'is-no' : 'is-na')}>{children}</div>
}

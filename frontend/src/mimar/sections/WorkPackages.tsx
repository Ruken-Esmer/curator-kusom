import { useMimar } from '../state'
import { Page, Panel, Pill } from '../ui'
import { SCREEN_LABEL, WORK_PACKAGES, type Task, type WorkPackage } from '../workPackages'

const MONTHS = 36

function taskState(t: Task, o: any): { tone: 'ok' | 'plain' | 'warn'; text: string } {
  if (t.outside) return { tone: 'plain', text: 'sistem dışında' }
  if (t.note) return { tone: 'warn', text: 'kısmen' }
  const s = t.status?.(o)
  if (s) return { tone: 'ok', text: 'sistemde kaydı var' }
  return { tone: 'plain', text: 'henüz kayıt yok' }
}

// a horizontal month ruler with one bar per row
function Gantt({ rows, from = 1, to = MONTHS, onRow }: {
  rows: { label: string; sub?: string; months: [number, number]; key: string }[]
  from?: number; to?: number; onRow?: (key: string) => void
}) {
  const span = to - from + 1
  const left = (m: number) => `${((m - from) / span) * 100}%`
  const width = (a: number, b: number) => `${((b - a + 1) / span) * 100}%`
  const ticks = Array.from({ length: span }, (_, i) => from + i).filter((m) => m === from || m % 6 === 0 || m === to)
  return (
    <div className="text-[13px]">
      <div className="grid" style={{ gridTemplateColumns: '220px 1fr' }}>
        <div />
        <div className="relative h-6 border-b border-zinc-300">
          {ticks.map((m) => (
            <span key={m} className="absolute -translate-x-1/2 text-[11px] text-zinc-500" style={{ left: `calc(${left(m)} + ${50 / span}%)` }}>{m}</span>
          ))}
        </div>
        {rows.map((r) => (
          <div key={r.key} className="contents">
            <button onClick={() => onRow?.(r.key)} disabled={!onRow}
              className="text-left pr-3 py-2 border-b border-zinc-100 hover:text-[var(--brand)] disabled:hover:text-inherit">
              <span className="font-semibold">{r.label}</span>
              {r.sub && <span className="block text-[12px] text-zinc-500 leading-snug">{r.sub}</span>}
            </button>
            <div className="relative border-b border-zinc-100">
              {from === 1 && to === MONTHS && [12, 24].map((m) => (
                <span key={m} className="absolute top-0 bottom-0 border-l border-dashed border-zinc-300" style={{ left: left(m + 1) }} />
              ))}
              <div className="absolute top-1/2 -translate-y-1/2 h-5 rounded-sm text-[11px] text-white flex items-center px-1.5 whitespace-nowrap overflow-hidden"
                style={{ left: left(r.months[0]), width: width(r.months[0], r.months[1]), background: 'var(--brand)' }}>
                {r.months[0]}–{r.months[1]}
              </div>
            </div>
          </div>
        ))}
      </div>
      <p className="mt-2 text-[12px] text-zinc-500">Proje ayları resmî başlangıçtan itibaren sayılır (1–36). Kesikli çizgiler yıl sonlarını gösterir.</p>
    </div>
  )
}

function counts(wp: WorkPackage, o: any) {
  const inSystem = wp.tasks.filter((t) => !t.outside)
  return { inSystem: inSystem.length, recorded: inSystem.filter((t) => t.status?.(o)).length, outside: wp.tasks.length - inSystem.length }
}

export function ProjectHome({ overview: o }: { overview: any }) {
  const go = useMimar((s) => s.go)
  return (
    <Page title="MİMAR projesi"
      lead="TÜBİTAK 1001 başvurusundaki altı iş paketi. Bir pakete tıklayınca hedefi, görevleri, başarı ölçütü ve sistemdeki ekranları açılır.">
      <Panel title="İş-zaman çizelgesi">
        <Gantt rows={WORK_PACKAGES.map((w) => ({ key: w.id, label: `İP${w.no} · ${w.short}`, sub: `önem %${w.weight}`, months: w.months }))}
          onRow={(k) => go(k as any)} />
      </Panel>
      <div className="grid gap-4 mt-4" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(330px, 1fr))' }}>
        {WORK_PACKAGES.map((w) => {
          const c = counts(w, o)
          return (
            <button key={w.id} onClick={() => go(w.id)} className="text-left rounded-md border border-zinc-300 bg-white p-4 hover:border-[var(--brand)]">
              <div className="flex justify-between items-baseline gap-2">
                <span className="font-semibold">İP{w.no} · {w.short}</span>
                <span className="text-[12px] text-zinc-500 whitespace-nowrap">{w.months[0]}–{w.months[1]}. ay</span>
              </div>
              <p className="text-[13px] text-zinc-600 mt-1.5 leading-snug">{w.goal}</p>
              <p className="text-[12px] text-zinc-500 mt-3">
                {w.tasks.length} görev · {c.inSystem > 0 ? `${c.recorded}/${c.inSystem} sistem görevinin kaydı var` : 'tamamı sistem dışında'}
                {c.outside > 0 && c.inSystem > 0 ? ` · ${c.outside} görev sistem dışında` : ''}
              </p>
            </button>
          )
        })}
      </div>
      <p className="mt-4 text-[12px] text-zinc-500">
        “Sistemde kaydı var” yalnızca ilgili kaydın sistemde bulunduğunu gösterir; görevin bilimsel olarak tamamlandığı anlamına gelmez.
        Sentetik demo kurulduysa bu kayıtlar örnek veriye aittir.
      </p>
    </Page>
  )
}

export function WorkPackagePage({ id, overview: o }: { id: WorkPackage['id']; overview: any }) {
  const go = useMimar((s) => s.go)
  const setStep = useMimar((s) => s.setStep)
  const w = WORK_PACKAGES.find((x) => x.id === id)!
  return (
    <Page title={`İP${w.no} · ${w.name}`} lead={w.goal}>
      <p className="text-[13px] text-zinc-600 -mt-2 mb-4">
        Dönem: <b>{w.months[0]}–{w.months[1]}. aylar</b> · Önem: <b>%{w.weight}</b> · Araştırma sorusu: <b>{w.rq}</b>
      </p>

      <Panel title="Görevler">
        <Gantt from={w.months[0]} to={w.months[1]}
          rows={w.tasks.map((t) => ({ key: t.no, label: t.no, sub: t.title, months: t.months }))} />
        <table className="m-table mt-5">
          <thead><tr><th>No</th><th>Görev</th><th>Aylar</th><th>Kim</th><th>Sistemde</th><th>Durum</th></tr></thead>
          <tbody>{w.tasks.map((t) => {
            const st = taskState(t, o)
            return (
              <tr key={t.no}>
                <td>{t.no}</td>
                <td>{t.title}{t.note && <div className="text-[12px] text-zinc-500 mt-0.5">{t.note}</div>}</td>
                <td className="whitespace-nowrap">{t.months[0]}–{t.months[1]}</td>
                <td className="text-[12px]">{t.who}</td>
                <td className="text-[12px]">
                  {t.screen ? <button onClick={() => go(t.screen!)} className="text-[var(--brand)] underline underline-offset-2 text-left">{SCREEN_LABEL[t.screen]}</button>
                    : <span className="text-zinc-500">{t.outside}</span>}
                </td>
                <td className="whitespace-nowrap"><Pill tone={st.tone}>{st.text}</Pill></td>
              </tr>
            )
          })}</tbody>
        </table>
      </Panel>

      <div className="grid gap-4 mt-4" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))' }}>
        <Panel title="Başarı ölçütü">
          <ul className="list-disc pl-5 text-[14px] flex flex-col gap-1.5">{w.success.map((s) => <li key={s}>{s}</li>)}</ul>
        </Panel>
        <Panel title="Ara çıktılar">
          <ul className="list-disc pl-5 text-[14px] flex flex-col gap-1.5">{w.outputs.map((s) => <li key={s}>{s}</li>)}</ul>
        </Panel>
      </div>
      <p className="mt-4 text-[14px]">
        <button onClick={() => { setStep(w.no - 1); go('senaryo') }} className="text-[var(--brand)] underline underline-offset-2">Osteoartrit örneğinde İP{w.no} adımını gör</button>
      </p>
      <p className="mt-2 text-[12px] text-zinc-500">Metinler başvuru formunun (13.09.2026) 3.1 bölümünden sadeleştirilmiştir; bağlayıcı ifade formdaki metindir.</p>
    </Page>
  )
}

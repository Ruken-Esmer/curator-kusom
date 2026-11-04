// MİMAR API client — every call carries the user's bearer token.
const BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''
const PREFIX = `${BASE}/api/v1/mimar`

let token = ''
try { token = sessionStorage.getItem('mimar_token') ?? '' } catch { /* storage unavailable */ }

export function setToken(t: string) {
  token = t
  try { t ? sessionStorage.setItem('mimar_token', t) : sessionStorage.removeItem('mimar_token') } catch { /* ignore */ }
}
export const getToken = () => token

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

async function req<T = any>(method: string, path: string, body?: unknown, isForm = false): Promise<T> {
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'
  const res = await fetch(`${PREFIX}${path}`, {
    method, headers,
    body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
  })
  const text = await res.text()
  if (!res.ok) {
    let msg = text
    try { msg = JSON.parse(text).detail ?? text } catch { /* plain text */ }
    throw new ApiError(res.status, typeof msg === 'string' ? msg : JSON.stringify(msg))
  }
  try { return JSON.parse(text) as T } catch { return text as unknown as T }
}

export const api = {
  get: <T = any>(p: string) => req<T>('GET', p),
  post: <T = any>(p: string, b: unknown = {}) => req<T>('POST', p, b),
  patch: <T = any>(p: string, b: unknown) => req<T>('PATCH', p, b),
  upload: <T = any>(p: string, file: File, extra: Record<string, string> = {}) => {
    const fd = new FormData()
    fd.append('file', file)
    Object.entries(extra).forEach(([k, v]) => fd.append(k, v))
    return req<T>('POST', p, fd, true)
  },
  download: async (p: string, filename: string) => {
    const res = await fetch(`${PREFIX}${p}`, { headers: { Authorization: `Bearer ${token}` } })
    if (!res.ok) throw new ApiError(res.status, await res.text())
    const url = URL.createObjectURL(await res.blob())
    const a = document.createElement('a')
    a.href = url; a.download = filename; a.click()
    URL.revokeObjectURL(url)
  },
}

import type {
  ChatMessage, CurriculumTree, HealthStatus,
  Language, QueryResponse, SubgraphData,
} from '@/types'

const BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`)
  return res.json()
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

// ── Chat ─────────────────────────────────────────────────

export const chatApi = {
  query: (
    query: string,
    language: Language,
    history: ChatMessage[],
    institution = 'koc_university',
  ): Promise<QueryResponse> =>
    post('/api/v1/chat', {
      query,
      language,
      conversation_history: history,
      institution,
    }),
}

// ── Curriculum ────────────────────────────────────────────

export const curriculumApi = {
  getTree: (institution = 'koc_university', language: Language = 'en'): Promise<CurriculumTree> =>
    get(`/api/v1/curriculum/tree?institution=${institution}&language=${language}`),

  getBlock: (blockId: string) =>
    get(`/api/v1/curriculum/block/${blockId}`),

  getPrerequisites: (blockId: string) =>
    get(`/api/v1/curriculum/prerequisites/${blockId}`),
}

// ── Graph ─────────────────────────────────────────────────

export const graphApi = {
  getSubgraph: (nodeId: string, depth = 2): Promise<SubgraphData> =>
    get(`/api/v1/graph/subgraph/${nodeId}?depth=${depth}`),
}

// ── Health ────────────────────────────────────────────────

export const healthApi = {
  check: (): Promise<HealthStatus> => get('/health'),
}

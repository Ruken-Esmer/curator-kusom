// ─── Domain Types ────────────────────────────────────────

export type Language = 'en' | 'tr'

export type QueryType = 'factual' | 'relational' | 'pathway' | 'advisory' | 'audit' | 'unknown'

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface Citation {
  block_id: string
  block_name: string
  year: number
  relevance: number
}

export interface PathwayStep {
  order: number
  block_id: string
  block_name: string
  year: number
  reason: string
}

export interface RetrievedChunk {
  id: string
  content: string
  source: string
  source_type: string
  score: number
  metadata: Record<string, unknown>
}

export interface QueryResponse {
  answer: string
  query_type: QueryType
  citations: Citation[]
  pathway: PathwayStep[]
  retrieved_chunks: RetrievedChunk[]
  language: Language
  processing_time_ms: number
}

// ─── Curriculum Tree ─────────────────────────────────────

export interface BlockInfo {
  id: string
  name: string
  weeks: string
  departments: string[]
  topics?: string[]
  prerequisite_ids?: string[]
}

export interface YearInfo {
  year: number
  name: string
  blocks: BlockInfo[]
}

export interface CurriculumTree {
  institution: string
  years: YearInfo[]
}

// ─── Graph Types ─────────────────────────────────────────

export interface GraphNode {
  id: string
  label: string
  name: string
  year?: number
  color?: string
}

export interface GraphEdge {
  source: string
  target: string
  type: string
}

export interface SubgraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

// ─── Health ──────────────────────────────────────────────

export interface HealthStatus {
  status: string
  version: string
  neo4j: boolean
  vector_store: boolean
  llm: string
}

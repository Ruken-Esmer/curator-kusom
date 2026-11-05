import { create } from 'zustand'
import type {
  ChatMessage, Citation, CurriculumTree,
  Language, PathwayStep, QueryType, Suggestion,
} from '@/types'

interface AppStore {
  // ── Language ──────────────────────────────────────────
  language: Language
  setLanguage: (l: Language) => void

  // ── Chat ──────────────────────────────────────────────
  messages: ChatMessage[]
  isLoading: boolean
  lastQueryType: QueryType | null
  lastCitations: Citation[]
  lastPathway: PathwayStep[]
  lastSuggestions: Suggestion[]
  lastProcessingMs: number
  addMessage: (m: ChatMessage) => void
  setLoading: (v: boolean) => void
  setLastResult: (opts: {
    queryType: QueryType
    citations: Citation[]
    pathway: PathwayStep[]
    suggestions?: Suggestion[]
    processingMs: number
  }) => void
  clearChat: () => void

  // ── Curriculum Sidebar ────────────────────────────────
  curriculum: CurriculumTree | null
  setCurriculum: (c: CurriculumTree) => void
  activeYear: number | null
  setActiveYear: (y: number | null) => void
  activeBlockId: string | null
  setActiveBlockId: (id: string | null) => void

  // ── Graph Panel ───────────────────────────────────────
  graphNodeId: string | null
  setGraphNodeId: (id: string | null) => void
  graphPanelOpen: boolean
  setGraphPanelOpen: (v: boolean) => void
}

export const useStore = create<AppStore>((set) => ({
  // Language
  language: 'en',
  setLanguage: (language) => set({ language }),

  // Chat
  messages: [],
  isLoading: false,
  lastQueryType: null,
  lastCitations: [],
  lastPathway: [],
  lastSuggestions: [],
  lastProcessingMs: 0,
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  setLoading: (isLoading) => set({ isLoading }),
  setLastResult: ({ queryType, citations, pathway, suggestions, processingMs }) =>
    set({
      lastQueryType: queryType,
      lastCitations: citations,
      lastPathway: pathway,
      lastSuggestions: suggestions ?? [],
      lastProcessingMs: processingMs,
    }),
  clearChat: () =>
    set({
      messages: [],
      lastQueryType: null,
      lastCitations: [],
      lastPathway: [],
      lastSuggestions: [],
    }),

  // Curriculum
  curriculum: null,
  setCurriculum: (curriculum) => set({ curriculum }),
  activeYear: null,
  setActiveYear: (activeYear) => set({ activeYear }),
  activeBlockId: null,
  setActiveBlockId: (activeBlockId) => set({ activeBlockId }),

  // Graph
  graphNodeId: null,
  setGraphNodeId: (graphNodeId) => set({ graphNodeId }),
  graphPanelOpen: false,
  setGraphPanelOpen: (graphPanelOpen) => set({ graphPanelOpen }),
}))

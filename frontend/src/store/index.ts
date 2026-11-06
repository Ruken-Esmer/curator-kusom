import { create } from 'zustand'
import type {
  ChatMessage, Citation, CurriculumTree,
  Language, PathwayStep, QueryType,
} from '@/types'

interface AppStore {
  // Language
  language: Language
  setLanguage: (l: Language) => void

  // Chat
  messages: ChatMessage[]
  isLoading: boolean
  lastQueryType: QueryType | null
  lastCitations: Citation[]
  lastPathway: PathwayStep[]
  lastProcessingMs: number
  addMessage: (m: ChatMessage) => void
  setLoading: (v: boolean) => void
  setLastResult: (opts: {
    queryType: QueryType
    citations: Citation[]
    pathway: PathwayStep[]
    processingMs: number
  }) => void
  clearChat: () => void

  // Curriculum Sidebar
  curriculum: CurriculumTree | null
  setCurriculum: (c: CurriculumTree) => void
  activeYear: number | null
  setActiveYear: (y: number | null) => void
  activeBlockId: string | null
  setActiveBlockId: (id: string | null) => void

  // Graph Panel
  graphNodeId: string | null
  setGraphNodeId: (id: string | null) => void
  graphPanelOpen: boolean
  setGraphPanelOpen: (v: boolean) => void
}

export const useStore = create<AppStore>((set) => ({
  // Language
  language: 'tr',
  setLanguage: (language) => set({ language }),

  // Chat
  messages: [],
  isLoading: false,
  lastQueryType: null,
  lastCitations: [],
  lastPathway: [],
  lastProcessingMs: 0,
  addMessage: (m) => set((s) => ({ messages: [...s.messages, m] })),
  setLoading: (isLoading) => set({ isLoading }),
  setLastResult: ({ queryType, citations, pathway, processingMs }) =>
    set({
      lastQueryType: queryType,
      lastCitations: citations,
      lastPathway: pathway,
      lastProcessingMs: processingMs,
    }),
  clearChat: () =>
    set({
      messages: [],
      lastQueryType: null,
      lastCitations: [],
      lastPathway: [],
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

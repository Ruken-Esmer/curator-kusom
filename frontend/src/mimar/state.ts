import { create } from 'zustand'

export type Section =
  | 'overview' | 'data' | 'analysis' | 'plan' | 'review' | 'findings'
  | 'validation' | 'as5' | 'impact' | 'stats' | 'audit' | 'people' | 'playground'
  | 'home' | 'senaryo' | 'scan' | 'wp1' | 'wp2' | 'wp3' | 'wp4' | 'wp5' | 'wp6'

interface MimarState {
  user: any | null
  setUser: (u: any | null) => void
  section: Section
  go: (s: Section) => void
  analysisId: string | null
  setAnalysisId: (id: string | null) => void
  refreshKey: number
  step: number
  setStep: (n: number) => void
  refresh: () => void
}

export const useMimar = create<MimarState>((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  section: 'home',
  go: (section) => set({ section }),
  analysisId: null,
  setAnalysisId: (analysisId) => set({ analysisId }),
  refreshKey: 0,
  step: 0,
  setStep: (step) => set({ step }),
  refresh: () => set((s) => ({ refreshKey: s.refreshKey + 1 })),
}))

export const hasRole = (u: any, ...roles: string[]) => !!u && roles.some((r) => u.roles?.includes(r))

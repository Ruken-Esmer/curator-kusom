import { useEffect, useRef } from 'react'
import { chatApi, curriculumApi } from '@/services/api'
import { useStore } from '@/store'

// ── useCurriculum ─────────────────────────────────────────

export function useCurriculum() {
  const { language, curriculum, setCurriculum } = useStore()

  useEffect(() => {
    curriculumApi
      .getTree('koc_university', language)
      .then(setCurriculum)
      .catch(console.error)
  }, [language, setCurriculum])

  return curriculum
}

// ── useChat ───────────────────────────────────────────────

export function useChat() {
  const {
    language,
    messages,
    isLoading,
    lastCitations,
    lastPathway,
    lastQueryType,
    lastProcessingMs,
    addMessage,
    setLoading,
    setLastResult,
    clearChat,
  } = useStore()

  const sendQuery = async (query: string) => {
    if (!query.trim() || isLoading) return
    addMessage({ role: 'user', content: query })
    setLoading(true)
    try {
      const res = await chatApi.query(query, language, messages)
      addMessage({ role: 'assistant', content: res.answer })
      setLastResult({
        queryType: res.query_type,
        citations: res.citations,
        pathway: res.pathway,
        suggestions: res.suggestions,
        processingMs: res.processing_time_ms,
      })
    } catch (err) {
      const msg = language === 'tr'
        ? 'Sunucu hatası. Lütfen tekrar deneyin.'
        : 'Server error. Please try again.'
      addMessage({ role: 'assistant', content: msg })
    } finally {
      setLoading(false)
    }
  }

  return {
    messages,
    isLoading,
    lastCitations,
    lastPathway,
    lastQueryType,
    lastProcessingMs,
    sendQuery,
    clearChat,
  }
}

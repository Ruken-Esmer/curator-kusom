import { useCallback, useEffect, useRef, useState } from 'react'
import { X, GitBranch, ZoomIn, ZoomOut } from 'lucide-react'
import { graphApi } from '@/services/api'
import { useStore } from '@/store'
import type { SubgraphData } from '@/types'

const YEAR_COLOURS: Record<string, string> = {
  Year:        '#0F6E56',
  Block:       '#185FA5',
  Topic:       '#854F0B',
  Department:  '#993C1D',
  Competency:  '#533AB7',
}

function getColour(label: string) {
  return YEAR_COLOURS[label] ?? '#888'
}

// Simple SVG-based force layout (no external lib needed in base build)

function GraphCanvas({ data, nodeId }: { data: SubgraphData; nodeId: string }) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [scale, setScale] = useState(1)
  const W = 420, H = 360

  // Simple circular placement
  const nodes = data.nodes.filter(Boolean).slice(0, 30)
  const edges = data.edges.filter(Boolean).slice(0, 40)

  const positions: Record<string, { x: number; y: number }> = {}
  nodes.forEach((n, i) => {
    if (n.id === nodeId) {
      positions[n.id] = { x: W / 2, y: H / 2 }
    } else {
      const angle = (2 * Math.PI * i) / Math.max(nodes.length - 1, 1)
      const radius = Math.min(W, H) * 0.35
      positions[n.id] = {
        x: W / 2 + radius * Math.cos(angle),
        y: H / 2 + radius * Math.sin(angle),
      }
    }
  })

  return (
    <div className="relative" style={{ transform: `scale(${scale})`, transformOrigin: 'top left' }}>
      <svg ref={svgRef} viewBox={`0 0 ${W} ${H}`} className="w-full">
        <defs>
          <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 Z" fill="#aaa" />
          </marker>
        </defs>
        {edges.map((e, i) => {
          const s = positions[e.source]
          const t = positions[e.target]
          if (!s || !t) return null
          return (
            <g key={i}>
              <line
                x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                stroke="#ccc" strokeWidth={1}
                strokeDasharray={e.type === 'PREREQUISITE_OF' ? '4,2' : undefined}
                markerEnd="url(#arrow)"
              />
            </g>
          )
        })}
        {nodes.map((n) => {
          const pos = positions[n.id]
          if (!pos) return null
          const colour = getColour(n.label)
          const isCentre = n.id === nodeId
          return (
            <g key={n.id}>
              <circle
                cx={pos.x} cy={pos.y}
                r={isCentre ? 20 : 14}
                fill={isCentre ? colour : `${colour}22`}
                stroke={colour} strokeWidth={isCentre ? 2 : 1.5}
              />
              <text
                x={pos.x} y={pos.y + 4}
                textAnchor="middle" fontSize={isCentre ? 9 : 8}
                fontWeight={isCentre ? '600' : '400'}
                fill={isCentre ? 'white' : colour}
              >
                {n.id.length > 5 ? n.id.slice(0, 5) : n.id}
              </text>
              <text
                x={pos.x} y={pos.y + (isCentre ? 32 : 26)}
                textAnchor="middle" fontSize={7}
                fill="#888"
              >
                {(n.name || '').slice(0, 18)}
              </text>
            </g>
          )
        })}
      </svg>
    </div>
  )
}

// Panel

export default function GraphPanel() {
  const { graphNodeId, graphPanelOpen, setGraphPanelOpen } = useStore()
  const [data, setData] = useState<SubgraphData | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!graphNodeId) return
    setLoading(true)
    graphApi
      .getSubgraph(graphNodeId, 2)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [graphNodeId])

  if (!graphPanelOpen || !graphNodeId) return null

  return (
    <aside className="w-[460px] shrink-0 border-l border-zinc-200 dark:border-zinc-700 flex flex-col">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-200 dark:border-zinc-700 shrink-0">
        <div className="flex items-center gap-2">
          <GitBranch size={14} className="text-teal-700" />
          <span className="text-sm font-medium">Knowledge Graph</span>
          {graphNodeId && (
            <code className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 font-mono text-zinc-600">
              {graphNodeId}
            </code>
          )}
        </div>
        <button
          onClick={() => setGraphPanelOpen(false)}
          className="p-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-400 transition-colors"
        >
          <X size={14} />
        </button>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {loading && (
          <div className="flex items-center justify-center h-48 text-sm text-zinc-400">
            Loading graph…
          </div>
        )}
        {!loading && data && (
          <>
            <div className="mb-3">
              <GraphCanvas data={data} nodeId={graphNodeId} />
            </div>
            <div className="text-xs text-zinc-500 space-y-1">
              <p className="font-medium">
                {data.nodes.length} nodes · {data.edges.length} edges
              </p>
              <div className="flex flex-wrap gap-1.5 mt-2">
                {Object.entries(YEAR_COLOURS).map(([label, colour]) => (
                  <span key={label} className="flex items-center gap-1 text-[10px]">
                    <span className="inline-block w-2.5 h-2.5 rounded-full" style={{ background: colour }} />
                    {label}
                  </span>
                ))}
              </div>
            </div>
          </>
        )}
        {!loading && !data && (
          <div className="flex items-center justify-center h-48 text-sm text-zinc-400">
            Select a block to view its graph
          </div>
        )}
      </div>
    </aside>
  )
}

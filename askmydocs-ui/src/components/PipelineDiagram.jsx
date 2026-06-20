const STATUS_FILL = {
  idle:  '#e5e7eb',
  start: '#fbbf24',
  done:  '#10b981',
  error: '#ef4444',
  warn:  '#f97316',
  info:  '#3b82f6',
}

const AGENT_MAP = {
  topic_planner: 'planner',
  ingestion:     'ingestion',
  currency:      'currency',
  memory:        'memory',
  rag:           'rag',
  error_handler: 'planner',   // show on planner box
  critic_1:      'critic1',
  writer:        'writer',
  critic_2:      'critic2',
}

function nodeColor(id, agentStatus) {
  const raw = agentStatus[id] || agentStatus[Object.keys(AGENT_MAP).find(k => AGENT_MAP[k] === id)] || 'idle'
  return STATUS_FILL[raw] || STATUS_FILL.idle
}

function NodeBox({ x, y, w, h, label, color, running }) {
  return (
    <g>
      <rect
        x={x} y={y} width={w} height={h} rx={8}
        fill={color}
        stroke={color === STATUS_FILL.idle ? '#d1d5db' : color}
        strokeWidth={1.5}
        style={running ? { filter: 'brightness(1.12)' } : {}}
      />
      <text
        x={x + w / 2} y={y + h / 2 + 1}
        textAnchor="middle" dominantBaseline="middle"
        fontSize={11} fontWeight={500} fill={color === STATUS_FILL.idle ? '#6b7280' : '#fff'}
        fontFamily="'Noto Sans JP', sans-serif"
      >
        {label}
      </text>
    </g>
  )
}

function Arrow({ x1, y1, x2, y2 }) {
  return (
    <line
      x1={x1} y1={y1} x2={x2} y2={y2}
      stroke="#d1d5db" strokeWidth={1.5}
      markerEnd="url(#arrow)"
    />
  )
}

export default function PipelineDiagram({ agentStatus = {} }) {
  const nodeStatus = (nodeId) => {
    const reversed = Object.entries(AGENT_MAP).filter(([, v]) => v === nodeId).map(([k]) => k)
    for (const key of reversed) {
      if (agentStatus[key]) return agentStatus[key]
    }
    return 'idle'
  }

  const color = (id) => STATUS_FILL[nodeStatus(id)] || STATUS_FILL.idle
  const running = (id) => nodeStatus(id) === 'start'

  return (
    <svg viewBox="0 0 760 160" style={{ width: '100%', maxWidth: 760, display: 'block' }}>
      <defs>
        <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L0,6 L6,3 z" fill="#d1d5db" />
        </marker>
      </defs>

      {/* Planner */}
      <NodeBox x={10}  y={60}  w={90}  h={40} label="Planner"   color={color('planner')}   running={running('planner')} />

      {/* Phase 1 bracket */}
      <rect x={118} y={4} width={148} height={152} rx={8} fill="none" stroke="#e5e7eb" strokeWidth={1} strokeDasharray="4 3" />
      <text x={124} y={16} fontSize={9} fill="#9ca3af" fontFamily="'Noto Sans JP', sans-serif">Phase 1</text>

      {/* Ingestion / Currency / Memory */}
      <NodeBox x={126} y={14}  w={132} h={36} label="Ingestion"  color={color('ingestion')} running={running('ingestion')} />
      <NodeBox x={126} y={62}  w={132} h={36} label="Currency"   color={color('currency')}  running={running('currency')} />
      <NodeBox x={126} y={110} w={132} h={36} label="Memory"     color={color('memory')}    running={running('memory')} />

      {/* RAG */}
      <NodeBox x={296} y={60} w={80} h={40} label="RAG"      color={color('rag')}     running={running('rag')} />

      {/* Critic 1 */}
      <NodeBox x={398} y={60} w={84} h={40} label="Critic 1"  color={color('critic1')} running={running('critic1')} />

      {/* Writer */}
      <NodeBox x={506} y={38} w={80} h={40} label="Writer"   color={color('writer')}  running={running('writer')} />

      {/* Critic 2 */}
      <NodeBox x={506} y={84} w={80} h={40} label="Critic 2" color={color('critic2')} running={running('critic2')} />

      {/* Done */}
      <NodeBox x={616} y={60} w={60} h={40} label="Done"     color={color('done')}    running={false} />

      {/* Arrows */}
      {/* Planner → Phase 1 inputs */}
      <Arrow x1={100} y1={80} x2={124} y2={32} />
      <Arrow x1={100} y1={80} x2={124} y2={80} />
      <Arrow x1={100} y1={80} x2={124} y2={128} />

      {/* Phase 1 → RAG */}
      <Arrow x1={258} y1={32}  x2={294} y2={74} />
      <Arrow x1={258} y1={80}  x2={294} y2={80} />
      <Arrow x1={258} y1={128} x2={294} y2={86} />

      {/* RAG → Critic1 */}
      <Arrow x1={376} y1={80} x2={396} y2={80} />

      {/* Critic1 → Writer */}
      <Arrow x1={482} y1={72} x2={504} y2={60} />

      {/* Writer ↔ Critic2 */}
      <path d="M 586,82 C 600,82 600,102 586,102" fill="none" stroke="#d1d5db" strokeWidth={1.5} markerEnd="url(#arrow)" />
      <path d="M 586,102 C 600,102 600,82 586,82"  fill="none" stroke="#d1d5db" strokeWidth={1.5} markerEnd="url(#arrow)" />

      {/* Critic2 → Done */}
      <Arrow x1={586} y1={90} x2={614} y2={82} />

      {/* Legend */}
      {[['idle','Idle'],['start','Running'],['done','Done'],['error','Error']].map(([s,l], i) => (
        <g key={s} transform={`translate(${10 + i * 90}, 148)`}>
          <circle cx={5} cy={5} r={5} fill={STATUS_FILL[s]} />
          <text x={14} y={9} fontSize={9} fill="#6b7280" fontFamily="'Noto Sans JP', sans-serif">{l}</text>
        </g>
      ))}
    </svg>
  )
}

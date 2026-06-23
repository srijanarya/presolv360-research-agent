// ── Brief contract ────────────────────────────────────────────────────────────

export type SourceStatus =
  | 'ok'
  | 'paywalled'
  | 'js_required'
  | 'timeout'
  | 'empty'
  | 'error'

export interface BriefSource {
  id: string
  url: string
  title: string
  status: SourceStatus
  fetch_method: string | null
  error: string | null
}

export type Classification = 'consensus' | 'contested' | 'outlier'
export type Stance = 'supports' | 'contradicts'
export type Confidence = 'high' | 'medium' | 'low'

export interface ClusterMember {
  source_id: string
  stance: Stance
  claim_text: string
  supporting_quote: string
  confidence: Confidence
}

export interface ClaimCluster {
  id: string
  statement: string
  classification: Classification
  members: ClusterMember[]
}

export interface Gap {
  description: string
  rationale: string
}

export interface BriefMeta {
  sources_ok: number
  sources_failed: number
  model_reason: string
  model_extract: string
}

export interface Brief {
  topic: string
  generated_at: string
  sources: BriefSource[]
  claim_clusters: ClaimCluster[]
  gaps: Gap[]
  meta: BriefMeta
}

// ── SSE event types ───────────────────────────────────────────────────────────

export type PipelineStage = 'fetch' | 'extract' | 'reason' | 'synthesize'

export interface StageStartedEvent {
  type: 'stage_started'
  stage: PipelineStage
  total?: number
}

export interface SourceStatusEvent {
  type: 'source_status'
  id: string
  url: string
  status: SourceStatus
  title: string
}

export interface StageCompletedEvent {
  type: 'stage_completed'
  stage: PipelineStage
  ok?: number
  failed?: number
  claims?: number
  clusters?: number
  gaps?: number
}

export interface DoneEvent {
  type: 'done'
  brief: Brief
}

export interface ErrorEvent {
  type: 'error'
  error: string
}

export type SSEEvent =
  | StageStartedEvent
  | SourceStatusEvent
  | StageCompletedEvent
  | DoneEvent
  | ErrorEvent

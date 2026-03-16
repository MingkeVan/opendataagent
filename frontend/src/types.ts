export interface SkillSummary {
  id: string
  name: string
  version: string
  description: string
  engine: string
  renderers: Record<string, unknown>
}

export interface Conversation {
  id: string
  title: string
  skillId: string
  skillVersion: string
  status: string
  activeRunId: string | null
  updatedAt: string
}

export interface Message {
  id: string
  conversationId: string
  runId: string | null
  role: 'user' | 'assistant'
  uiParts: UiPart[]
  contentBlocks?: Record<string, unknown>[]
  traceSummary?: Record<string, unknown> | null
  finalText?: string | null
  status: string
  createdAt: string
}

export interface UiPart {
  type: string
  id?: string
  stepId?: string
  title?: string
  summary?: string
  content?: string
  text?: string
  toolName?: string
  state?: string
  status?: string
  input?: unknown
  output?: unknown
  error?: string
  artifactId?: string
  artifactType?: string
  columns?: string[]
  rows?: unknown[]
  spec?: Record<string, unknown>
  [key: string]: unknown
}

export interface StreamEvent {
  version?: string
  kind?: string
  runId?: string
  messageId?: string | null
  seq: number
  type?: string
  payload?: Record<string, unknown>
  [key: string]: unknown
}

export interface ArtifactResponse {
  id: string
  runId: string
  conversationId: string
  artifactType: string
  mimeType: string
  sizeBytes: number
  contentJson: Record<string, unknown> | null
  contentText: string | null
  metadataJson: Record<string, unknown>
  createdAt: string
}

export interface SandboxDetail {
  source: UiPart
  artifact: ArtifactResponse | null
  isLoading: boolean
  error: string
}

export function isTextPart(part: UiPart): boolean {
  return part.type === 'text'
}

export function isReasoningPart(part: UiPart): boolean {
  return part.type === 'reasoning'
}

export function isToolCallPart(part: UiPart): boolean {
  return part.type === 'tool-call' || part.type === 'tool_call'
}

export function isDataChartPart(part: UiPart): boolean {
  return part.type === 'data-chart'
}

export function isDataTablePart(part: UiPart): boolean {
  return part.type === 'data-table'
}

export function isDataArtifactPart(part: UiPart): boolean {
  return part.type === 'data-artifact'
}

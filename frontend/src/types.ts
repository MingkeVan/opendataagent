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
  status: string
  createdAt: string
}

export type UiPart = {
  type: string
  id?: string
  stepId?: string
  [key: string]: unknown
}

export interface StreamEvent {
  seq: number
  type: string
  [key: string]: unknown
}


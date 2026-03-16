import type { ArtifactResponse, Conversation, Message, SkillSummary } from '../types'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    ...init,
  })
  if (!response.ok) {
    const bodyText = await response.text()
    let message = bodyText || `Request failed: ${response.status}`
    if (bodyText) {
      try {
        const body = JSON.parse(bodyText)
        message = typeof body?.detail === 'string' ? body.detail : JSON.stringify(body)
      } catch {
        message = bodyText
      }
    }
    throw new Error(message)
  }
  return response.json() as Promise<T>
}

export function getApiBase() {
  return API_BASE
}

export function fetchSkills() {
  return request<SkillSummary[]>('/api/skills')
}

export function fetchConversations() {
  return request<Conversation[]>('/api/conversations')
}

export function createConversation(skillId: string, title?: string) {
  return request<Conversation>('/api/conversations', {
    method: 'POST',
    body: JSON.stringify({ skillId, title }),
  })
}

export function fetchConversation(conversationId: string) {
  return request<Conversation>(`/api/conversations/${conversationId}`)
}

export function fetchMessages(conversationId: string) {
  return request<Message[]>(`/api/conversations/${conversationId}/messages`)
}

export function sendMessage(conversationId: string, content: string) {
  return request<{ conversationId: string; userMessageId: string; assistantMessageId: string; runId: string; status: string }>(
    `/api/conversations/${conversationId}/messages`,
    {
      method: 'POST',
      body: JSON.stringify({ content, attachments: [] }),
    },
  )
}

export function cancelRun(runId: string) {
  return request<{ runId: string; status: string }>(`/api/runs/${runId}/cancel`, {
    method: 'POST',
  })
}

export function fetchArtifact(artifactId: string) {
  return request<ArtifactResponse>(`/api/artifacts/${artifactId}`)
}

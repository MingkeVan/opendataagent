import { computed, ref } from 'vue'
import {
  cancelRun,
  createConversation,
  fetchConversation,
  fetchConversations,
  fetchMessages,
  fetchSkills,
  getApiBase,
  sendMessage,
} from '../lib/api'
import { applyStreamEvent } from '../lib/stream'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import type { Conversation, Message, SkillSummary, StreamEvent, UiPart } from '../types'

export function useChat() {
  const renderMarkdown = (text: string): string => {
    if (!text) return ''
    return DOMPurify.sanitize(marked.parse(text) as string)
  }

  const skills = ref<SkillSummary[]>([
    { id: 'data-analyst', name: 'Data Analyst', version: '1.0.0', description: '', engine: 'claude-agent-sdk', renderers: {} }
  ])
  const conversations = ref<Conversation[]>([
    {
      id: 'conv-mock-1',
      title: 'Analyze Q3 Sales Data',
      skillId: 'data-analyst',
      skillVersion: '1.0.0',
      status: 'idle',
      activeRunId: null,
      updatedAt: new Date().toISOString()
    }
  ])
  const messages = ref<Message[]>([
    {
      id: 'msg-u-1',
      conversationId: 'conv-mock-1',
      role: 'user',
      status: 'completed',
      runId: 'run1',
      uiParts: [{ type: 'text', text: 'Can you analyze the Q3 sales data and let me know the total revenue, and show me the raw database output for the top 5 regions?' }],
      createdAt: new Date(Date.now() - 60000).toISOString()
    },
    {
      id: 'msg-a-1',
      conversationId: 'conv-mock-1',
      role: 'assistant',
      status: 'completed',
      runId: 'run1',
      createdAt: new Date(Date.now() - 50000).toISOString(),
      uiParts: [
        { 
          type: 'reasoning', 
          summary: 'Determine data sources and construct SQL', 
          content: 'I need to query the `sales_q3` table. First, I will aggregate the total revenue and then get the top 5 regions by grouping by region and ordering descending.', 
          durationMs: 1250 
        },
        { 
          type: 'tool_call', 
          toolCallId: 'call_abc123', 
          toolName: 'execute_sql', 
          input: { sql: 'SELECT region, SUM(revenue) as total FROM sales_q3 GROUP BY region ORDER BY total DESC LIMIT 5;' }, 
          status: 'success', 
          durationMs: 840,
          outputSummary: { rowCount: 5, status: 'ok' }
        },
        { 
          type: 'text', 
          text: 'The query was successful. The total revenue has been calculated and I retrieved the top 5 regions. Based on the data, **North America** and **Europe** make up over 70% of the Q3 revenue.\n\nLet me know if you need to visualize this.' 
        }
      ]
    }
  ])
  const selectedSkillId = ref('data-analyst')
  const activeConversationId = ref<string | null>('conv-mock-1')
  const composer = ref('')
  const isSending = ref(false)
  const runStatus = ref('idle')
  const activeRunId = ref<string | null>(null)
  const selectedDetail = ref<UiPart | null>(null)
  const errorMessage = ref('')
  const streamSeq = ref<Record<string, number>>({})
  let eventSource: EventSource | null = null

  const activeConversation = computed(() =>
    conversations.value.find((item: Conversation) => item.id === activeConversationId.value) ?? null,
  )

  const detailVisible = computed({
    get: () => selectedDetail.value !== null,
    set: (value: boolean) => {
      if (!value) {
        selectedDetail.value = null
      }
    },
  })

  const apiBase = getApiBase()

  function closeStream() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  }

  async function loadSkills() {
    skills.value = await fetchSkills()
    if (!selectedSkillId.value && skills.value.length) {
      selectedSkillId.value = skills.value[0].id
    }
  }

  async function loadConversations(selectFirst = false) {
    conversations.value = await fetchConversations()
    if (selectFirst && conversations.value.length && !activeConversationId.value) {
      await openConversation(conversations.value[0].id)
    }
  }

  async function openConversation(conversationId: string) {
    closeStream()
    activeConversationId.value = conversationId
    const [conversation, loadedMessages] = await Promise.all([
      fetchConversation(conversationId),
      fetchMessages(conversationId),
    ])
    upsertConversation(conversation)
    messages.value = loadedMessages
    if (conversation.activeRunId) {
      activeRunId.value = conversation.activeRunId
      runStatus.value = conversation.status
      startStream(conversation.activeRunId, 0)
    } else {
      activeRunId.value = null
      runStatus.value = 'idle'
    }
  }

  function upsertConversation(conversation: Conversation) {
    const index = conversations.value.findIndex((item: Conversation) => item.id === conversation.id)
    if (index === -1) {
      conversations.value.unshift(conversation)
    } else {
      conversations.value[index] = conversation
    }
  }

  function upsertAssistantMessage(runId: string, updater: (message: Message) => void) {
    let message = messages.value.find((item: Message) => item.runId === runId && item.role === 'assistant')
    if (!message) {
      message = {
        id: `local_${runId}`,
        conversationId: activeConversationId.value || '',
        runId,
        role: 'assistant',
        uiParts: [],
        status: 'streaming',
        createdAt: new Date().toISOString(),
      }
      messages.value.push(message)
    }
    updater(message)
    messages.value = [...messages.value]
  }

  function startStream(runId: string, afterSeq = 0) {
    closeStream()
    const lastSeq = streamSeq.value[runId] ?? afterSeq
    eventSource = new EventSource(`${apiBase}/api/runs/${runId}/stream?after_seq=${lastSeq}`)
    eventSource.onmessage = async (messageEvent) => {
      if (messageEvent.data === '[DONE]') {
        closeStream()
        runStatus.value = 'completed'
        activeRunId.value = null
        if (activeConversationId.value) {
          await openConversation(activeConversationId.value)
          await loadConversations()
        }
        return
      }
      const payload = JSON.parse(messageEvent.data) as StreamEvent
      streamSeq.value = { ...streamSeq.value, [runId]: payload.seq }
      if (payload.type === 'finish') {
        runStatus.value = 'completed'
      } else if (payload.type === 'abort') {
        runStatus.value = 'failed'
        errorMessage.value = String(payload.reason || 'Stream aborted')
      } else {
        runStatus.value = payload.type.startsWith('tool-') ? 'running-tool' : 'streaming'
      }
      upsertAssistantMessage(runId, (assistant) => {
        assistant.uiParts = applyStreamEvent(assistant.uiParts, payload)
        assistant.status = runStatus.value
      })
    }
    eventSource.onerror = () => {
      runStatus.value = 'interrupted'
      errorMessage.value = 'SSE 流连接中断，可刷新后继续恢复。'
      closeStream()
    }
  }

  async function createNewConversation() {
    if (!selectedSkillId.value) {
      return
    }
    const conversation = await createConversation(selectedSkillId.value)
    upsertConversation(conversation)
    await openConversation(conversation.id)
  }

  async function handleSend() {
    if (!composer.value.trim()) {
      return
    }
    errorMessage.value = ''
    isSending.value = true
    try {
      if (!activeConversationId.value) {
        await createNewConversation()
      }
      const conversationId = activeConversationId.value
      if (!conversationId) {
        throw new Error('未创建会话')
      }
      const text = composer.value.trim()
      composer.value = ''
      const payload = await sendMessage(conversationId, text)
      messages.value = await fetchMessages(conversationId)
      activeRunId.value = payload.runId
      runStatus.value = payload.status
      startStream(payload.runId, 0)
      await loadConversations()
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '发送消息失败'
    } finally {
      isSending.value = false
    }
  }

  async function handleCancel() {
    if (!activeRunId.value) {
      return
    }
    await cancelRun(activeRunId.value)
    runStatus.value = 'cancel_requested'
  }

  return {
    skills,
    conversations,
    messages,
    selectedSkillId,
    activeConversationId,
    composer,
    isSending,
    runStatus,
    activeRunId,
    selectedDetail,
    errorMessage,
    streamSeq,
    activeConversation,
    detailVisible,
    apiBase,
    loadSkills,
    loadConversations,
    openConversation,
    createNewConversation,
    handleSend,
    handleCancel,
    closeStream,
    renderMarkdown
  }
}


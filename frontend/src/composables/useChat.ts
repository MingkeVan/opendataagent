import { computed, onBeforeUnmount, ref } from 'vue'
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
import { type Conversation, type Message, type SkillSummary, type StreamEvent, type UiPart } from '../types'

const DEFAULT_CONVERSATION_TITLE = '新建会话'

function toErrorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

function normalizeUiPart(part: UiPart): UiPart {
  const nextType = part.type === 'tool_call' ? 'tool-call' : part.type
  if (nextType === 'tool-call') {
    return {
      ...part,
      type: nextType,
      id: String(part.id || part.toolCallId || ''),
      toolName: String(part.toolName || 'tool'),
      state: String(part.state || part.status || 'running'),
      input: part.input ?? null,
      output: part.output ?? part.outputSummary ?? null,
    }
  }
  return {
    ...part,
    type: nextType,
  }
}

function normalizeMessage(message: Message): Message {
  return {
    ...message,
    uiParts: Array.isArray(message.uiParts) ? message.uiParts.map((part) => normalizeUiPart(part)) : [],
  }
}

function compareMessages(left: Message, right: Message): number {
  const leftSequence = typeof left.sequenceNo === 'number' ? left.sequenceNo : Number.MAX_SAFE_INTEGER
  const rightSequence = typeof right.sequenceNo === 'number' ? right.sequenceNo : Number.MAX_SAFE_INTEGER
  if (leftSequence !== rightSequence) {
    return leftSequence - rightSequence
  }

  const leftTime = Date.parse(left.createdAt || '')
  const rightTime = Date.parse(right.createdAt || '')
  if (!Number.isNaN(leftTime) && !Number.isNaN(rightTime) && leftTime !== rightTime) {
    return leftTime - rightTime
  }

  return left.id.localeCompare(right.id)
}

function sortMessages(nextMessages: Message[]): Message[] {
  return [...nextMessages].sort(compareMessages)
}

export function useChat() {
  const renderMarkdown = (text: string): string => {
    if (!text) {
      return ''
    }
    return DOMPurify.sanitize(marked.parse(text) as string)
  }

  const skills = ref<SkillSummary[]>([])
  const conversations = ref<Conversation[]>([])
  const messages = ref<Message[]>([])
  const selectedSkillId = ref('')
  const activeConversationId = ref<string | null>(null)
  const composer = ref('')
  const isSending = ref(false)
  const isBootstrapping = ref(false)
  const runStatus = ref('idle')
  const activeRunId = ref<string | null>(null)
  const errorMessage = ref('')
  const streamSeq = ref<Record<string, number>>({})
  let eventSource: EventSource | null = null

  const activeConversation = computed(() =>
    conversations.value.find((item) => item.id === activeConversationId.value) ?? null,
  )

  const apiBase = getApiBase()

  onBeforeUnmount(() => {
    closeStream()
  })

  function closeStream() {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
  }

  function resetConversationState() {
    closeStream()
    activeConversationId.value = null
    activeRunId.value = null
    runStatus.value = 'idle'
    messages.value = []
  }

  function upsertConversation(conversation: Conversation) {
    const index = conversations.value.findIndex((item) => item.id === conversation.id)
    if (index === -1) {
      conversations.value.unshift(conversation)
      return
    }
    conversations.value[index] = conversation
    conversations.value = [...conversations.value]
  }

  function applyFirstPromptTitle(conversationId: string, prompt: string) {
    const title = prompt.trim()
    if (!title) {
      return
    }
    const existing = conversations.value.find((item) => item.id === conversationId)
    if (!existing || (existing.title && existing.title !== DEFAULT_CONVERSATION_TITLE)) {
      return
    }
    upsertConversation({
      ...existing,
      title,
      updatedAt: new Date().toISOString(),
    })
  }

  function upsertAssistantMessage(runId: string, updater: (message: Message) => void) {
    let message = messages.value.find((item) => item.runId === runId && item.role === 'assistant')
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
    const normalized = normalizeMessage(message)
    Object.assign(message, normalized)
    messages.value = sortMessages(messages.value)
  }

  async function initialize() {
    isBootstrapping.value = true
    errorMessage.value = ''
    try {
      await loadSkills()
      await loadConversations(true)
    } finally {
      isBootstrapping.value = false
    }
  }

  async function loadSkills() {
    try {
      const nextSkills = await fetchSkills()
      skills.value = nextSkills
      if (!skills.value.length) {
        selectedSkillId.value = ''
        return
      }
      const currentSelected = skills.value.some((skill) => skill.id === selectedSkillId.value)
      if (!currentSelected) {
        selectedSkillId.value = skills.value[0].id
      }
    } catch (error) {
      errorMessage.value = toErrorMessage(error, '加载技能列表失败')
      throw error
    }
  }

  async function loadConversations(selectFirst = false) {
    try {
      const nextConversations = await fetchConversations()
      conversations.value = nextConversations
      if (!nextConversations.length) {
        resetConversationState()
        return
      }
      const currentConversationExists = nextConversations.some((item) => item.id === activeConversationId.value)
      if (activeConversationId.value && currentConversationExists) {
        return
      }
      if (selectFirst || !activeConversationId.value || !currentConversationExists) {
        await openConversation(nextConversations[0].id)
      }
    } catch (error) {
      errorMessage.value = toErrorMessage(error, '加载会话列表失败')
      throw error
    }
  }

  async function openConversation(conversationId: string) {
    try {
      closeStream()
      activeConversationId.value = conversationId
      const [conversation, loadedMessages] = await Promise.all([
        fetchConversation(conversationId),
        fetchMessages(conversationId),
      ])
      upsertConversation(conversation)
      messages.value = sortMessages(loadedMessages.map((message) => normalizeMessage(message)))
      if (conversation.activeRunId) {
        activeRunId.value = conversation.activeRunId
        runStatus.value = conversation.status
        startStream(conversation.activeRunId, streamSeq.value[conversation.activeRunId] ?? 0)
      } else {
        activeRunId.value = null
        runStatus.value = conversation.status || 'idle'
      }
    } catch (error) {
      errorMessage.value = toErrorMessage(error, '打开会话失败')
      throw error
    }
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

      if (payload.kind === 'snapshot') {
        const snapshot = payload.payload as { uiParts?: UiPart[] } | undefined
        upsertAssistantMessage(runId, (assistant) => {
          assistant.uiParts = Array.isArray(snapshot?.uiParts)
            ? snapshot!.uiParts.map((part) => normalizeUiPart(part))
            : []
          assistant.status = runStatus.value
        })
        return
      }

      if (payload.kind === 'status') {
        const statusPayload = payload.payload as { runStatus?: string; reason?: string } | undefined
        runStatus.value = String(statusPayload?.runStatus || runStatus.value)
        if (statusPayload?.reason) {
          errorMessage.value = String(statusPayload.reason)
        }
        return
      }

      if (payload.kind === 'done') {
        runStatus.value = String((payload.payload as { runStatus?: string } | undefined)?.runStatus || 'completed')
        return
      }

      const streamPart = payload.payload as StreamEvent | undefined
      if (!streamPart?.type) {
        return
      }

      if (streamPart.type === 'finish') {
        runStatus.value = 'completed'
      } else {
        runStatus.value = String(streamPart.type).startsWith('tool-') ? 'running-tool' : 'streaming'
      }

      upsertAssistantMessage(runId, (assistant) => {
        assistant.uiParts = applyStreamEvent(assistant.uiParts, payload).map((part) => normalizeUiPart(part))
        assistant.status = runStatus.value
      })
    }

    eventSource.onerror = () => {
      runStatus.value = 'interrupted'
      errorMessage.value = 'SSE 流连接中断，可刷新后恢复最新状态。'
      closeStream()
    }
  }

  async function createNewConversation() {
    if (!selectedSkillId.value) {
      errorMessage.value = '当前没有可用技能，无法创建会话'
      return
    }
    try {
      const conversation = await createConversation(selectedSkillId.value)
      upsertConversation(conversation)
      await openConversation(conversation.id)
    } catch (error) {
      errorMessage.value = toErrorMessage(error, '创建会话失败')
      throw error
    }
  }

  async function startConversationWithPrompt(prompt: string) {
    const text = prompt.trim()
    if (!text) {
      return
    }
    if (!selectedSkillId.value) {
      errorMessage.value = '当前没有可用技能，无法创建会话'
      return
    }

    errorMessage.value = ''
    isSending.value = true
    try {
      closeStream()
      const conversation = await createConversation(selectedSkillId.value)
      upsertConversation(conversation)
      activeConversationId.value = conversation.id
      activeRunId.value = null
      runStatus.value = 'idle'
      messages.value = []
      applyFirstPromptTitle(conversation.id, text)

      const payload = await sendMessage(conversation.id, text)
      messages.value = sortMessages((await fetchMessages(conversation.id)).map((message) => normalizeMessage(message)))
      activeRunId.value = payload.runId
      runStatus.value = payload.status
      startStream(payload.runId, 0)
      await loadConversations()
    } catch (error) {
      errorMessage.value = toErrorMessage(error, '启动示例问题失败')
    } finally {
      isSending.value = false
    }
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
      applyFirstPromptTitle(conversationId, text)
      composer.value = ''
      const payload = await sendMessage(conversationId, text)
      messages.value = sortMessages((await fetchMessages(conversationId)).map((message) => normalizeMessage(message)))
      activeRunId.value = payload.runId
      runStatus.value = payload.status
      startStream(payload.runId, 0)
      await loadConversations()
    } catch (error) {
      errorMessage.value = toErrorMessage(error, '发送消息失败')
    } finally {
      isSending.value = false
    }
  }

  async function handleCancel() {
    if (!activeRunId.value) {
      return
    }
    try {
      await cancelRun(activeRunId.value)
      runStatus.value = 'cancel_requested'
    } catch (error) {
      errorMessage.value = toErrorMessage(error, '取消运行失败')
    }
  }

  return {
    skills,
    conversations,
    messages,
    selectedSkillId,
    activeConversationId,
    composer,
    isSending,
    isBootstrapping,
    runStatus,
    activeRunId,
    errorMessage,
    streamSeq,
    activeConversation,
    apiBase,
    initialize,
    loadSkills,
    loadConversations,
    openConversation,
    createNewConversation,
    startConversationWithPrompt,
    handleSend,
    handleCancel,
    closeStream,
    renderMarkdown,
  }
}

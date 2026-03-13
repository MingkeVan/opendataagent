<script setup lang="ts">
import { Connection, Plus, RefreshRight } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'
import MessageCard from './components/MessageCard.vue'
import { cancelRun, createConversation, fetchConversation, fetchConversations, fetchMessages, fetchSkills, getApiBase, sendMessage } from './lib/api'
import { applyStreamEvent } from './lib/stream'
import type { Conversation, Message, SkillSummary, StreamEvent, UiPart } from './types'

const skills = ref<SkillSummary[]>([])
const conversations = ref<Conversation[]>([])
const messages = ref<Message[]>([])
const selectedSkillId = ref('')
const activeConversationId = ref<string | null>(null)
const composer = ref('')
const isSending = ref(false)
const runStatus = ref('idle')
const activeRunId = ref<string | null>(null)
const selectedDetail = ref<UiPart | null>(null)
const errorMessage = ref('')
const streamSeq = ref<Record<string, number>>({})
let eventSource: EventSource | null = null

const activeConversation = computed(() =>
  conversations.value.find((item) => item.id === activeConversationId.value) ?? null,
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
  const index = conversations.value.findIndex((item) => item.id === conversation.id)
  if (index === -1) {
    conversations.value.unshift(conversation)
  } else {
    conversations.value[index] = conversation
  }
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

onMounted(async () => {
  await loadSkills()
  await loadConversations(true)
})
</script>

<template>
  <div class="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(223,196,137,0.38),_transparent_35%),linear-gradient(135deg,_#f5f1e7_0%,_#e7efe9_42%,_#dde8ec_100%)] text-ink">
    <div class="mx-auto flex min-h-screen max-w-[1600px] gap-6 px-4 py-5 lg:px-6">
      <aside class="flex w-full max-w-[320px] flex-col rounded-[2.2rem] border border-white/70 bg-white/80 p-4 shadow-panel backdrop-blur">
        <div class="mb-4 flex items-start justify-between gap-3">
          <div>
            <div class="text-xs uppercase tracking-[0.24em] text-ink/45">OpenDataAgent</div>
            <h1 class="mt-2 text-2xl font-semibold">Skill Chat</h1>
          </div>
          <el-button circle :icon="RefreshRight" @click="loadConversations()" />
        </div>

        <div class="mb-4 rounded-3xl bg-clay/70 p-3">
          <div class="mb-2 text-xs uppercase tracking-[0.18em] text-ink/50">Skill</div>
          <el-select v-model="selectedSkillId" placeholder="选择 skill" class="w-full">
            <el-option v-for="skill in skills" :key="skill.id" :label="`${skill.name} (${skill.version})`" :value="skill.id" />
          </el-select>
          <el-button class="mt-3 w-full" type="primary" :icon="Plus" @click="createNewConversation()">新建会话</el-button>
        </div>

        <div class="mb-3 flex items-center gap-2 rounded-2xl bg-ink px-3 py-2 text-sm text-white">
          <el-icon><Connection /></el-icon>
          <span>API: {{ apiBase }}</span>
        </div>

        <div class="flex-1 overflow-y-auto pr-1">
          <button
            v-for="conversation in conversations"
            :key="conversation.id"
            class="mb-3 w-full rounded-3xl border p-4 text-left transition"
            :class="
              activeConversationId === conversation.id
                ? 'border-emerald-400 bg-emerald-50 shadow-panel'
                : 'border-transparent bg-stone-50/80 hover:border-stone-200'
            "
            @click="openConversation(conversation.id)"
          >
            <div class="mb-1 line-clamp-1 text-sm font-semibold">{{ conversation.title }}</div>
            <div class="text-xs text-ink/55">{{ conversation.skillId }} · {{ conversation.status }}</div>
          </button>
        </div>
      </aside>

      <main class="flex min-h-[90vh] flex-1 flex-col rounded-[2.6rem] border border-white/70 bg-white/65 p-5 shadow-panel backdrop-blur">
        <header class="mb-4 flex flex-col gap-3 rounded-[2rem] bg-[#16302b] px-5 py-4 text-white lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div class="text-xs uppercase tracking-[0.24em] text-white/55">Conversation</div>
            <div class="mt-2 text-2xl font-semibold">{{ activeConversation?.title || '请选择或创建一个会话' }}</div>
            <div class="mt-2 text-sm text-white/70">
              {{ activeConversation ? `${activeConversation.skillId} · ${activeConversation.skillVersion}` : '当前支持多轮对话、历史持久化、thinking 时间线和 tool block。' }}
            </div>
          </div>
          <div class="flex items-center gap-3">
            <div class="rounded-full bg-white/10 px-4 py-2 text-sm">
              Run Status: <span class="font-semibold">{{ runStatus }}</span>
            </div>
            <el-button
              v-if="activeRunId"
              type="danger"
              plain
              @click="handleCancel()"
            >
              取消运行
            </el-button>
          </div>
        </header>

        <div class="mb-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <section class="rounded-[2rem] bg-white/70 p-4 shadow-panel">
            <div v-if="errorMessage" class="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {{ errorMessage }}
            </div>

            <div class="space-y-5 overflow-y-auto pr-1" style="max-height: calc(100vh - 290px)">
              <div v-if="messages.length === 0" class="flex min-h-[300px] items-center justify-center rounded-[2rem] border border-dashed border-stone-300 bg-stone-50/80 text-center text-ink/50">
                发送一条消息，验证多轮对话、thinking、tool call 和 chart render 的整条链路。
              </div>

              <MessageCard
                v-for="message in messages"
                :key="message.id"
                :message="message"
                @select-detail="selectedDetail = $event"
              />
            </div>
          </section>

          <aside class="rounded-[2rem] bg-[#f4efe3] p-4 shadow-panel">
            <div class="mb-3 text-xs uppercase tracking-[0.18em] text-ink/45">Timeline Hints</div>
            <div class="space-y-3 text-sm text-ink/70">
              <div class="rounded-2xl bg-white/70 p-3">1. `reasoning` 默认折叠，只显示摘要。</div>
              <div class="rounded-2xl bg-white/70 p-3">2. `tool-call` 展示输入、输出和状态。</div>
              <div class="rounded-2xl bg-white/70 p-3">3. `data-chart` 与 `data-table` 直接内嵌渲染。</div>
              <div class="rounded-2xl bg-white/70 p-3">4. 页面刷新后，若存在 `activeRunId`，会自动从头回放事件并继续 tail。</div>
            </div>
          </aside>
        </div>

        <footer class="mt-auto rounded-[2rem] bg-white/80 p-4 shadow-panel">
          <div class="mb-3 flex items-center justify-between">
            <div class="text-sm font-semibold text-ink">发送消息</div>
            <div class="text-xs text-ink/45">Enter 换行，点击按钮发送</div>
          </div>
          <el-input
            v-model="composer"
            type="textarea"
            :rows="4"
            resize="none"
            placeholder="例如：请用图表和表格说明最近七天订单趋势，并给出一句结论。"
          />
          <div class="mt-3 flex justify-end">
            <el-button type="primary" :loading="isSending" @click="handleSend()">发送并启动 Agent</el-button>
          </div>
        </footer>
      </main>
    </div>

    <el-drawer v-model="detailVisible" title="详情面板" size="40%">
      <pre class="overflow-auto rounded-3xl bg-stone-950 p-4 text-xs text-stone-100">{{ JSON.stringify(selectedDetail, null, 2) }}</pre>
    </el-drawer>
  </div>
</template>

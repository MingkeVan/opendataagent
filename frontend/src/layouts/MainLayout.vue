<script setup lang="ts">
import { CollectionTag, EditPen, Loading, Promotion, RefreshRight, Search, Warning } from '@element-plus/icons-vue'
import { computed, onMounted, ref } from 'vue'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { useChat } from '../composables/useChat'
import {
  isDataArtifactPart,
  isDataChartPart,
  isDataTablePart,
  isReasoningPart,
  isTextPart,
  isToolCallPart,
  type Message,
  type UiPart,
} from '../types'

use([GridComponent, TooltipComponent, LegendComponent, LineChart, BarChart, CanvasRenderer])

const chat = useChat()
const {
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
  activeConversation,
  initialize,
  loadConversations,
  openConversation,
  createNewConversation,
  startConversationWithPrompt,
  handleSend,
  handleCancel,
  renderMarkdown,
} = chat

const starterQuestions = [
  '这个月哪个用户产生的销售额最多？',
  '最近30天订单数量趋势',
  '按品类看本月销售额 Top 5',
  '数据库里有几个表？',
]

const UTC_PLUS_8_OFFSET_MS = 8 * 60 * 60 * 1000
const relativeTimeFormatter = new Intl.RelativeTimeFormat('zh-CN', { numeric: 'auto' })
const conversationSearch = ref('')

onMounted(async () => {
  await initialize()
})

function formatTime(isoString: string) {
  if (!isoString) {
    return ''
  }
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(isoString))
}

function parseServerUtcIso(isoString: string) {
  if (!isoString) {
    return null
  }
  const normalized = /z|[+-]\d{2}:\d{2}$/i.test(isoString) ? isoString : `${isoString}Z`
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function formatRelativeTimeUtc8(isoString: string) {
  const parsed = parseServerUtcIso(isoString)
  if (!parsed) {
    return ''
  }

  const nowUtc8 = Date.now() + UTC_PLUS_8_OFFSET_MS
  const targetUtc8 = parsed.getTime() + UTC_PLUS_8_OFFSET_MS
  const diffMs = targetUtc8 - nowUtc8
  const diffMinutes = Math.round(diffMs / 60000)

  if (Math.abs(diffMinutes) < 1) {
    return '刚刚'
  }
  if (Math.abs(diffMinutes) < 60) {
    return relativeTimeFormatter.format(diffMinutes, 'minute')
  }

  const diffHours = Math.round(diffMinutes / 60)
  if (Math.abs(diffHours) < 24) {
    return relativeTimeFormatter.format(diffHours, 'hour')
  }

  const diffDays = Math.round(diffHours / 24)
  if (Math.abs(diffDays) < 7) {
    return relativeTimeFormatter.format(diffDays, 'day')
  }

  const diffWeeks = Math.round(diffDays / 7)
  if (Math.abs(diffWeeks) < 5) {
    return relativeTimeFormatter.format(diffWeeks, 'week')
  }

  const diffMonths = Math.round(diffDays / 30)
  if (Math.abs(diffMonths) < 12) {
    return relativeTimeFormatter.format(diffMonths, 'month')
  }

  const diffYears = Math.round(diffDays / 365)
  return relativeTimeFormatter.format(diffYears, 'year')
}

function textParts(message: Message) {
  return message.uiParts.filter((part) => isTextPart(part))
}

function thinkingParts(message: Message) {
  return message.uiParts.filter(
    (part) => part.type === 'step' || isReasoningPart(part) || isToolCallPart(part),
  )
}

function chartParts(message: Message) {
  return message.uiParts.filter((part) => isDataChartPart(part))
}

function tableParts(message: Message) {
  return message.uiParts.filter((part) => isDataTablePart(part))
}

function artifactParts(message: Message) {
  return message.uiParts.filter((part) => isDataArtifactPart(part))
}

function toolInputPreview(part: UiPart) {
  if (part.input !== undefined && part.input !== null) {
    return JSON.stringify(part.input, null, 2)
  }
  if (typeof part.inputText === 'string' && part.inputText) {
    return part.inputText
  }
  return 'Pending...'
}

function toolOutputPreview(part: UiPart) {
  if (part.output !== undefined && part.output !== null) {
    return JSON.stringify(part.output, null, 2)
  }
  if (part.error) {
    return String(part.error)
  }
  return 'Pending...'
}

function tableColumns(part: UiPart): string[] {
  if (!Array.isArray(part.columns)) {
    return []
  }
  return part.columns.filter((column): column is string => typeof column === 'string')
}

function tableRows(part: UiPart): Record<string, unknown>[] {
  const columns = tableColumns(part)
  const rows = Array.isArray(part.rows) ? part.rows : []
  return rows.map((row, index) => {
    if (Array.isArray(row)) {
      const mapped = columns.reduce<Record<string, unknown>>((acc, column, columnIndex) => {
        acc[column] = row[columnIndex]
        return acc
      }, {})
      return { __rowKey: String(index), ...mapped }
    }
    if (row && typeof row === 'object') {
      return { __rowKey: String(index), ...(row as Record<string, unknown>) }
    }
    return { __rowKey: String(index), value: row }
  })
}

function chartOption(part: UiPart): Record<string, unknown> {
  return part.spec && typeof part.spec === 'object' ? (part.spec as Record<string, unknown>) : {}
}

function dataCardTitle(part: UiPart) {
  if (part.title) {
    return String(part.title)
  }
  if (isDataChartPart(part)) {
    return '图表结果'
  }
  if (isDataTablePart(part)) {
    return '表格结果'
  }
  return 'Artifact'
}

function dataCardLabel(part: UiPart) {
  if (isDataChartPart(part)) {
    return 'CHART'
  }
  if (isDataTablePart(part)) {
    return 'TABLE'
  }
  return 'ARTIFACT'
}

function toolStateClass(state?: string) {
  switch (state) {
    case 'output-ready':
      return 'border-[#B7EB8F] bg-[#F6FFED] text-[#389E0D]'
    case 'failed':
      return 'border-[#FFCCC7] bg-[#FFF2F0] text-[#CF1322]'
    case 'input-ready':
      return 'border-[#D6E4FF] bg-[#F0F5FF] text-[#1D39C4]'
    default:
      return 'border-[#D9D9D9] bg-white text-[#595959]'
  }
}

function isPlaceholderConversationTitle(title?: string) {
  const normalized = String(title || '').trim()
  return !normalized || normalized === '新建会话'
}

function conversationListTitle(conversation: { title: string }) {
  return isPlaceholderConversationTitle(conversation.title) ? '未开始提问' : conversation.title
}

function currentConversationTitle() {
  if (!activeConversation.value || isPlaceholderConversationTitle(activeConversation.value.title)) {
    return ''
  }
  return activeConversation.value.title
}

const filteredConversations = computed(() => {
  const keyword = conversationSearch.value.trim().toLowerCase()
  if (!keyword) {
    return conversations.value
  }
  return conversations.value.filter((conversation) => conversationListTitle(conversation).toLowerCase().includes(keyword))
})

const selectedSkillLabel = computed(() => {
  const skill = skills.value.find((item) => item.id === selectedSkillId.value)
  return skill ? `${skill.name} · ${skill.version}` : '未选择 Skill'
})
</script>

<template>
  <div class="style-f-root flex h-screen min-w-[1100px] overflow-hidden bg-transparent font-['IBM_Plex_Sans','PingFang_SC','Hiragino_Sans_GB',sans-serif] text-[#1F1F1F]">
    <aside class="sidebar-shell flex w-72 shrink-0 flex-col bg-[rgba(255,255,255,0.72)]">
      <div class="px-4 py-4">
        <div class="mb-3 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#667085]">
          <el-icon :size="13"><CollectionTag /></el-icon>
          <span>Skill市场</span>
        </div>
        <div class="mb-3 truncate px-3.5 text-sm font-medium text-[#344054]">{{ selectedSkillLabel }}</div>
        <el-select
          v-model="selectedSkillId"
          class="skill-select w-full"
          placeholder="选择 Skill"
          :disabled="!skills.length"
          :teleported="false"
        >
          <el-option
            v-for="skill in skills"
            :key="skill.id"
            :value="skill.id"
            :label="`${skill.name} · ${skill.version}`"
          >
            {{ skill.name }} · {{ skill.version }}
          </el-option>
        </el-select>
      </div>

      <div class="px-4 py-3">
        <div class="mb-2 flex items-center justify-between">
          <div class="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#667085]">会话历史</div>
          <div class="flex items-center gap-2">
            <div class="text-[11px] text-[#98A2B3]">{{ filteredConversations.length }}</div>
            <button
              class="secondary-action flex h-8 w-8 items-center justify-center rounded-lg bg-transparent text-[#98A2B3] transition-colors hover:bg-[#EEF4FF] hover:text-[#1677FF]"
              title="刷新会话"
              @click="loadConversations()"
            >
              <el-icon :size="14"><RefreshRight /></el-icon>
            </button>
          </div>
        </div>
        <button
          class="sidebar-primary-action mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-[#EEF4FF] text-[#1677FF] transition-colors hover:bg-[#E0ECFF]"
          title="新增会话"
          @click="createNewConversation()"
        >
          <el-icon :size="16"><EditPen /></el-icon>
        </button>
        <div class="relative">
          <el-icon class="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#98A2B3]"><Search /></el-icon>
          <input
            v-model="conversationSearch"
            class="sidebar-search h-10 w-full rounded-lg border-0 bg-[#F1F4F8] pl-9 pr-3 text-sm text-[#344054] outline-none transition-colors placeholder:text-[#98A2B3] focus:bg-[#EAF2FF]"
            placeholder="搜索会话标题"
          />
        </div>
      </div>

      <div class="flex-1 overflow-y-auto p-3">
        <div
          v-if="!conversations.length && !isBootstrapping"
          class="empty-state rounded-xl border border-dashed border-[#D8E0EA] bg-white px-4 py-5 text-sm text-[#8C8C8C]"
        >
          还没有会话记录。
        </div>

        <div
          v-else-if="!filteredConversations.length"
          class="empty-state rounded-xl border border-dashed border-[#D8E0EA] bg-white px-4 py-5 text-sm text-[#8C8C8C]"
        >
          没有匹配的会话。
        </div>

        <button
          v-for="conversation in filteredConversations"
          :key="conversation.id"
          class="history-item mb-1.5 flex w-full min-w-0 items-center justify-between gap-3 rounded-xl px-3.5 py-3 text-left transition-colors"
          :class="
            activeConversationId === conversation.id
              ? 'bg-[#EEF5FF]'
              : 'bg-transparent hover:bg-[#F8FAFD]'
          "
          @click="openConversation(conversation.id)"
        >
          <div class="min-w-0 flex-1 truncate text-sm font-medium text-[#1F1F1F]">
            {{ conversationListTitle(conversation) }}
          </div>
          <span class="shrink-0 text-[11px] text-[#8C8C8C]">
            {{ formatRelativeTimeUtc8(conversation.updatedAt) }}
          </span>
        </button>
      </div>
    </aside>

    <main class="main-shell flex min-w-0 flex-1 flex-col bg-[#F7F8FA]">
      <header class="topbar flex h-14 shrink-0 items-center justify-between border-b border-[#E5EAF1] bg-[#F7F8FA] px-5">
        <div class="flex min-w-0 items-center gap-3">
          <div class="flex items-center gap-2">
            <div class="h-3.5 w-3.5 rounded-md bg-[#1677FF]"></div>
            <span class="text-sm font-semibold tracking-[0.08em] text-[#1F1F1F]">OpenDataAgent</span>
          </div>
          <template v-if="currentConversationTitle()">
            <div class="h-4 w-px bg-[#D9D9D9]"></div>
            <div class="truncate text-xs text-[#595959]">
              {{ currentConversationTitle() }}
            </div>
          </template>
        </div>

        <div class="flex items-center gap-3 text-xs">
          <div
            class="flex items-center gap-2 rounded-full border px-3 py-1.5"
            :class="activeRunId ? 'border-[#B8D2F8] bg-[#EDF4FF] text-[#175CD3]' : 'border-[#D7DFEA] bg-white text-[#667085]'"
          >
            <el-icon v-if="activeRunId" class="is-loading"><Loading /></el-icon>
            <span>{{ runStatus }}</span>
          </div>

          <button
            v-if="activeRunId"
            class="flex h-9 items-center justify-center rounded-lg border border-[#F4C7C7] bg-white px-3 text-[#C24141] transition-colors hover:bg-[#FFF4F3]"
            @click="handleCancel()"
          >
            Stop Run
          </button>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto p-8">
        <div v-if="isBootstrapping" class="flex h-full items-center justify-center text-sm text-[#8C8C8C]">
          正在加载前后端状态...
        </div>

        <div
          v-else-if="!activeConversation"
          class="empty-state flex h-full items-center justify-center rounded-2xl border border-dashed border-[#D8E0EA] bg-white text-sm text-[#8C8C8C]"
        >
          <div class="mx-auto max-w-[640px] space-y-4 px-6 text-center">
            <div>从左侧会话历史中继续，或直接选择一个示例问题开始。</div>
            <div class="grid gap-2 text-left sm:grid-cols-2">
              <button
                v-for="question in starterQuestions"
                :key="`empty-${question}`"
                class="starter-button rounded-lg border border-[#DDE4EE] bg-white px-3 py-3 text-sm leading-6 text-[#434343] transition-colors hover:border-[#A9C4F5] hover:bg-[#F7FAFF]"
                :disabled="isSending || !!activeRunId"
                @click="startConversationWithPrompt(question)"
              >
                {{ question }}
              </button>
            </div>
          </div>
        </div>

        <div
          v-else-if="!messages.length"
          class="empty-state flex h-full items-center justify-center rounded-2xl border border-dashed border-[#D8E0EA] bg-white text-sm text-[#8C8C8C]"
        >
          <div class="mx-auto max-w-[640px] space-y-4 px-6 text-center">
            <div>当前会话还没有消息。你可以直接输入问题，或从下面任选一个示例开始。</div>
            <div class="grid gap-2 text-left sm:grid-cols-2">
              <button
                v-for="question in starterQuestions"
                :key="`idle-${question}`"
                class="starter-button rounded-lg border border-[#DDE4EE] bg-white px-3 py-3 text-sm leading-6 text-[#434343] transition-colors hover:border-[#A9C4F5] hover:bg-[#F7FAFF]"
                :disabled="isSending || !!activeRunId"
                @click="startConversationWithPrompt(question)"
              >
                {{ question }}
              </button>
            </div>
          </div>
        </div>

        <div v-else class="mx-auto w-full max-w-[980px] space-y-10">
          <div v-for="message in messages" :key="message.id" class="flex flex-col">
            <div v-if="message.role === 'user'" class="ml-auto flex max-w-[82%] min-w-[240px] flex-col items-end">
              <div class="mb-1 text-[10px] uppercase tracking-[0.2em] text-[#1D39C4]">
                User · {{ formatTime(message.createdAt) }}
              </div>
              <div class="user-bubble border border-[#CFE0FF] bg-[#EEF4FF] px-4 py-3 text-sm text-[#1D39C4]">
                <div
                  v-for="(part, index) in textParts(message)"
                  :key="`${message.id}-user-${index}`"
                  class="markdown-body break-words leading-6"
                  v-html="renderMarkdown(String(part.text || ''))"
                ></div>
              </div>
            </div>

            <div v-else class="mr-auto w-full max-w-[860px]">
              <div class="mb-3 flex items-center justify-between border-b border-[#E6EBF2] pb-2 text-[10px] uppercase tracking-[0.2em] text-[#8C8C8C]">
                <span class="font-semibold text-[#389E0D]">Agent</span>
                <span>{{ formatTime(message.createdAt) }}</span>
              </div>

              <div v-if="thinkingParts(message).length" class="mb-4">
                <details class="surface-card group rounded-xl border border-[#E1E7EF] bg-white">
                  <summary class="flex cursor-pointer items-center justify-between px-3 py-2 text-xs text-[#595959]">
                    <span>
                      <span class="mr-2 inline-block transition-transform group-open:rotate-90">▶</span>
                      Thinking Process
                    </span>
                    <span>{{ thinkingParts(message).length }} parts</span>
                  </summary>

                  <div class="border-t border-[#E8E8E8] px-3 py-3">
                    <template v-for="(part, index) in thinkingParts(message)" :key="`${message.id}-thinking-${index}`">
                      <div
                        v-if="part.type === 'step'"
                        class="mb-3 flex items-center justify-between rounded-lg border border-[#E1E7EF] bg-[#FBFCFE] px-3 py-2 text-xs"
                      >
                        <div>
                          <div class="font-semibold text-[#1F1F1F]">{{ part.title || '执行步骤' }}</div>
                          <div class="mt-1 text-[#8C8C8C]">{{ part.stepId }}</div>
                        </div>
                        <span class="rounded-sm border border-[#D9D9D9] px-2 py-1 text-[#595959]">{{ part.status }}</span>
                      </div>

                      <div
                        v-else-if="isReasoningPart(part)"
                        class="mb-3 rounded-lg border border-[#DFE7F1] bg-[#FBFCFE] px-3 py-3"
                      >
                        <div class="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#595959]">Reasoning</div>
                        <div
                          class="markdown-body break-words text-sm leading-6 text-[#434343]"
                          v-html="renderMarkdown(String(part.summary || part.content || '...'))"
                        ></div>
                      </div>

                      <div
                        v-else-if="isToolCallPart(part)"
                        class="surface-card mb-3 rounded-xl border border-[#E1E7EF] bg-white p-3"
                      >
                        <div class="mb-3 flex items-center justify-between gap-3">
                          <div class="min-w-0">
                            <div class="truncate font-mono text-xs text-[#1F1F1F]">{{ part.toolName }}()</div>
                            <div class="mt-1 text-[11px] text-[#8C8C8C]">{{ part.id }}</div>
                          </div>
                          <span class="rounded-sm border px-2 py-1 text-[11px]" :class="toolStateClass(part.state)">
                            {{ part.state }}
                          </span>
                        </div>

                        <div class="grid gap-3 lg:grid-cols-2">
                          <div>
                            <div class="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8C8C8C]">Input</div>
                            <pre class="overflow-x-auto rounded-sm border border-[#E8E8E8] bg-[#FAFAFA] p-2 text-[11px] leading-5 text-[#434343]">{{ toolInputPreview(part) }}</pre>
                          </div>
                          <div>
                            <div class="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8C8C8C]">Output</div>
                            <pre class="overflow-x-auto rounded-sm border border-[#E8E8E8] bg-[#FAFAFA] p-2 text-[11px] leading-5 text-[#434343]">{{ toolOutputPreview(part) }}</pre>
                          </div>
                        </div>
                      </div>
                    </template>
                  </div>
                </details>
              </div>

              <div
                v-for="(part, index) in textParts(message)"
                :key="`${message.id}-text-${index}`"
                class="mb-4 last:mb-0"
              >
                <div
                  class="markdown-body break-words text-sm leading-6 text-[#1F1F1F]"
                  v-html="renderMarkdown(String(part.text || ''))"
                ></div>
              </div>

              <div v-if="chartParts(message).length" class="mt-4 space-y-3">
                <div
                  v-for="(part, index) in chartParts(message)"
                  :key="`${message.id}-chart-${index}`"
                  class="surface-card rounded-xl border border-[#E1E7EF] bg-white p-4"
                >
                  <div class="mb-3 flex items-center gap-2">
                    <span class="rounded-sm border border-[#D9D9D9] bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#595959]">
                      {{ dataCardLabel(part) }}
                    </span>
                    <span class="text-sm font-medium text-[#1F1F1F]">{{ dataCardTitle(part) }}</span>
                  </div>
                  <VChart class="h-[320px] w-full rounded-lg bg-[#FBFCFE]" autoresize :option="chartOption(part)" />
                  <div v-if="part.summary" class="mt-3 text-sm leading-6 text-[#595959]">
                    {{ part.summary }}
                  </div>
                </div>
              </div>

              <div v-if="tableParts(message).length" class="mt-4 space-y-3">
                <div
                  v-for="(part, index) in tableParts(message)"
                  :key="`${message.id}-table-${index}`"
                  class="surface-card rounded-xl border border-[#E1E7EF] bg-white p-4"
                >
                  <div class="mb-3 flex items-center gap-2">
                    <span class="rounded-sm border border-[#D9D9D9] bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#595959]">
                      {{ dataCardLabel(part) }}
                    </span>
                    <span class="text-sm font-medium text-[#1F1F1F]">{{ dataCardTitle(part) }}</span>
                  </div>
                  <el-table :data="tableRows(part)" size="small" stripe row-key="__rowKey" style="width: 100%">
                    <el-table-column
                      v-for="column in tableColumns(part)"
                      :key="column"
                      :prop="column"
                      :label="column"
                      min-width="120"
                    />
                  </el-table>
                  <div v-if="part.summary" class="mt-3 text-sm leading-6 text-[#595959]">
                    {{ part.summary }}
                  </div>
                </div>
              </div>

              <div v-if="artifactParts(message).length" class="mt-4 space-y-2">
                <div
                  v-for="(part, index) in artifactParts(message)"
                  :key="`${message.id}-artifact-${index}`"
                  class="surface-card rounded-xl border border-[#E1E7EF] bg-white px-4 py-4"
                >
                  <div class="mb-2 flex items-center gap-2">
                    <span class="rounded-sm border border-[#D9D9D9] bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#595959]">
                      {{ dataCardLabel(part) }}
                    </span>
                    <span class="text-sm font-medium text-[#1F1F1F]">{{ dataCardTitle(part) }}</span>
                  </div>
                  <div class="text-sm leading-6 text-[#595959]">
                    {{ part.summary || '结果已生成，但当前仅保留摘要展示。' }}
                  </div>
                </div>
              </div>

              <div
                v-if="!message.uiParts.length && message.status !== 'completed'"
                class="empty-state rounded-xl border border-dashed border-[#D8E0EA] bg-white px-4 py-4 text-sm text-[#8C8C8C]"
              >
                等待 Worker 产出事件流...
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="shrink-0 border-t border-[#E5EAF1] bg-[#F8FAFC] p-4">
        <div class="mx-auto w-full max-w-[980px]">
          <div v-if="errorMessage" class="mb-3 flex items-center gap-2 rounded-lg border border-[#FFCCC7] bg-[#FFF2F0] px-3 py-2 text-sm text-[#CF1322]">
            <el-icon><Warning /></el-icon>
            <span>{{ errorMessage }}</span>
          </div>

          <div class="composer-shell relative rounded-xl border border-[#DDE4EE] bg-[#F7F8FA]">
            <textarea
              v-model="composer"
              class="min-h-[88px] w-full resize-none rounded-xl border-0 bg-[#F7F8FA] px-4 pb-8 pt-3 pr-28 text-sm leading-6 text-[#1F1F1F] outline-none placeholder:text-[#98A2B3]"
              placeholder="输入 SQL、自然语言问题或执行指令..."
              @keydown.enter.exact.prevent="handleSend()"
            ></textarea>
            <div class="pointer-events-none absolute bottom-3 left-4 text-[11px] text-[#98A2B3]">
              Enter 发送，Shift + Enter 换行
            </div>
            <button
              class="primary-action absolute bottom-3 right-3 flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-[#1677FF] bg-[#1677FF] text-white transition-colors hover:bg-[#3B82F6] disabled:border-[#CAD1DB] disabled:bg-[#CAD1DB]"
              :disabled="isSending || !selectedSkillId"
              @click="handleSend()"
              :title="isSending ? '发送中' : '发送'"
              aria-label="发送"
            >
              <el-icon v-if="isSending" class="is-loading"><Loading /></el-icon>
              <el-icon v-else><Promotion /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.style-f-root {
  background: #f5f7fb;
}

.sidebar-shell,
.history-item,
.empty-state {
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.035);
}

.sidebar-shell,
.topbar {
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}

.main-shell,
.topbar,
.surface-card,
.composer-shell {
  box-shadow: none !important;
}

.history-item,
.surface-card,
.empty-state,
.composer-shell,
.starter-button {
  border-color: #e4eaf2;
}

.history-item {
  border-radius: 14px;
}

.history-item:hover,
.starter-button:hover,
.secondary-action:hover,
.primary-action:hover {
  transform: translateY(-1px);
}

.user-bubble {
  border-radius: 14px !important;
  box-shadow: 0 10px 20px rgba(23, 92, 211, 0.06);
}

.skill-select :deep(.el-select__wrapper) {
  min-height: 42px;
  border: 1px solid #d7dfea;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.03);
  background: rgba(255, 255, 255, 0.92);
  padding: 0 12px;
  transition:
    border-color 0.2s ease,
    background-color 0.2s ease,
    box-shadow 0.2s ease;
}

.skill-select :deep(.el-select__wrapper:hover) {
  border-color: #1677ff;
}

.skill-select :deep(.el-select__wrapper.is-focused) {
  border-color: #1677ff;
  box-shadow: 0 8px 16px rgba(22, 119, 255, 0.08);
}

.skill-select :deep(.el-select__selected-item) {
  color: #1f1f1f;
  font-size: 14px;
}

.skill-select :deep(.el-select__placeholder) {
  color: #8c8c8c;
}

.skill-select :deep(.el-select-dropdown) {
  border-radius: 12px;
}

.secondary-action,
.primary-action,
.starter-button,
.history-item {
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.18s ease;
}

.starter-button:hover,
.history-item:hover,
.secondary-action:hover,
.primary-action:hover {
  box-shadow: 0 8px 16px rgba(15, 23, 42, 0.045);
}

.surface-card {
  box-shadow: none !important;
}

.composer-shell {
  box-shadow: none !important;
}

details > summary {
  list-style: none;
}

details > summary::-webkit-details-marker {
  display: none;
}

.markdown-body :deep(p) {
  margin: 0 0 0.45rem;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 0.3rem 0 0.45rem;
  padding-left: 1.1rem;
}

.markdown-body :deep(li + li) {
  margin-top: 0.18rem;
}

.markdown-body :deep(table) {
  margin: 0.45rem 0;
}

.markdown-body :deep(pre) {
  overflow-x: auto;
  border: 1px solid #e8e8e8;
  background: #fafafa;
  padding: 10px 12px;
  margin: 0.45rem 0;
  border-radius: 6px;
}

.markdown-body :deep(code) {
  font-family:
    "IBM Plex Mono",
    "SFMono-Regular",
    Consolas,
    monospace;
  font-size: 0.92em;
}

:deep(.el-table),
:deep(.el-table th.el-table__cell),
:deep(.el-table tr),
:deep(.el-table td.el-table__cell),
:deep(.el-table__inner-wrapper::before) {
  box-shadow: none;
}
</style>

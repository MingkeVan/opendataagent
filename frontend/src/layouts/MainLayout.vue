<script setup lang="ts">
import { Connection, DataBoard, Document, Loading, Plus, RefreshRight, Warning } from '@element-plus/icons-vue'
import { computed, onMounted } from 'vue'
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
  selectedDetail,
  errorMessage,
  activeConversation,
  apiBase,
  initialize,
  loadConversations,
  openConversation,
  createNewConversation,
  handleSend,
  handleCancel,
  inspectPart,
  clearSelectedDetail,
  renderMarkdown,
} = chat

onMounted(async () => {
  await initialize()
})

const sandboxContent = computed<UiPart | null>(() => {
  const contentJson = selectedDetail.value?.artifact?.contentJson
  if (contentJson && typeof contentJson === 'object' && 'type' in contentJson) {
    return contentJson as UiPart
  }
  return selectedDetail.value?.source ?? null
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

function formatDateTime(isoString?: string) {
  if (!isoString) {
    return ''
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(isoString))
}

function textParts(message: Message) {
  return message.uiParts.filter((part) => isTextPart(part))
}

function thinkingParts(message: Message) {
  return message.uiParts.filter(
    (part) => part.type === 'step' || isReasoningPart(part) || isToolCallPart(part),
  )
}

function artifactCards(message: Message) {
  return message.uiParts.filter(
    (part) => isDataChartPart(part) || isDataTablePart(part) || isDataArtifactPart(part),
  )
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

function tableColumns(part: UiPart | null): string[] {
  if (!Array.isArray(part?.columns)) {
    return []
  }
  return part.columns.filter((column): column is string => typeof column === 'string')
}

function tableRows(part: UiPart | null): Record<string, unknown>[] {
  const columns = tableColumns(part)
  const rows = Array.isArray(part?.rows) ? part.rows : []
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

function chartOption(part: UiPart | null): Record<string, unknown> {
  return part?.spec && typeof part.spec === 'object' ? (part.spec as Record<string, unknown>) : {}
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

function sandboxPayload() {
  if (!selectedDetail.value) {
    return ''
  }
  return JSON.stringify(selectedDetail.value.artifact ?? selectedDetail.value.source, null, 2)
}
</script>

<template>
  <div class="style-f-root flex h-screen min-w-[1200px] overflow-hidden bg-[#FAFAFA] font-['IBM_Plex_Sans','PingFang_SC','Hiragino_Sans_GB',sans-serif] text-[#1F1F1F]">
    <aside class="flex w-64 shrink-0 flex-col border-r border-[#D9D9D9] bg-[#FAFAFA]">
      <div class="flex h-12 shrink-0 items-center justify-between border-b border-[#D9D9D9] px-3">
        <div>
          <div class="text-[11px] font-semibold uppercase tracking-[0.18em] text-[#595959]">Explorer</div>
          <div class="text-[10px] text-[#8C8C8C]">{{ conversations.length }} Conversations</div>
        </div>
        <div class="flex items-center gap-1">
          <button
            class="flex h-7 w-7 items-center justify-center border border-[#D9D9D9] bg-white text-[#595959] transition-colors hover:border-[#1677FF] hover:text-[#1677FF]"
            title="刷新会话"
            @click="loadConversations()"
          >
            <el-icon :size="14"><RefreshRight /></el-icon>
          </button>
          <button
            class="flex h-7 w-7 items-center justify-center border border-[#1677FF] bg-[#1677FF] text-white transition-colors hover:bg-[#4096FF]"
            title="新建会话"
            @click="createNewConversation()"
          >
            <el-icon :size="14"><Plus /></el-icon>
          </button>
        </div>
      </div>

      <div class="border-b border-[#D9D9D9] px-3 py-3">
        <div class="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#595959]">Skill</div>
        <select
          v-model="selectedSkillId"
          class="h-9 w-full border border-[#D9D9D9] bg-white px-2 text-sm text-[#1F1F1F] outline-none transition-colors hover:border-[#1677FF] focus:border-[#1677FF]"
        >
          <option v-if="!skills.length" value="">暂无可用 Skill</option>
          <option v-for="skill in skills" :key="skill.id" :value="skill.id">
            {{ skill.name }} · {{ skill.version }}
          </option>
        </select>
      </div>

      <div class="flex-1 overflow-y-auto p-1">
        <div
          v-if="!conversations.length && !isBootstrapping"
          class="px-3 py-4 text-sm text-[#8C8C8C]"
        >
          还没有会话记录。
        </div>

        <button
          v-for="conversation in conversations"
          :key="conversation.id"
          class="mb-1 flex w-full flex-col border px-3 py-2 text-left transition-colors"
          :class="
            activeConversationId === conversation.id
              ? 'border-[#1677FF] bg-[#E6F4FF]'
              : 'border-transparent bg-transparent hover:border-[#D9D9D9] hover:bg-white'
          "
          @click="openConversation(conversation.id)"
        >
          <div class="truncate text-sm font-medium text-[#1F1F1F]">{{ conversation.title }}</div>
          <div class="mt-1 flex items-center justify-between text-[11px] text-[#8C8C8C]">
            <span>{{ conversation.status }}</span>
            <span>{{ formatTime(conversation.updatedAt) }}</span>
          </div>
        </button>
      </div>
    </aside>

    <main class="flex min-w-0 flex-1 flex-col border-r border-[#D9D9D9] bg-white">
      <header class="flex h-12 shrink-0 items-center justify-between border-b border-[#D9D9D9] bg-[#FAFAFA] px-4">
        <div class="flex min-w-0 items-center gap-3">
          <div class="flex items-center gap-2">
            <div class="h-3 w-3 bg-[#1677FF]"></div>
            <span class="text-sm font-semibold tracking-[0.08em] text-[#1F1F1F]">OpenDataAgent</span>
          </div>
          <div class="h-4 w-px bg-[#D9D9D9]"></div>
          <div class="truncate text-xs text-[#595959]">
            {{ activeConversation?.title || '未选中会话' }}
          </div>
        </div>

        <div class="flex items-center gap-3 text-xs">
          <div class="hidden items-center gap-2 text-[#595959] md:flex">
            <el-icon><Connection /></el-icon>
            <span class="font-mono">{{ apiBase }}</span>
          </div>

          <div
            class="flex items-center gap-2 border px-2 py-1"
            :class="activeRunId ? 'border-[#91Caff] bg-[#E6F4FF] text-[#0958D9]' : 'border-[#D9D9D9] bg-white text-[#595959]'"
          >
            <el-icon v-if="activeRunId" class="is-loading"><Loading /></el-icon>
            <span>{{ runStatus }}</span>
          </div>

          <button
            v-if="activeRunId"
            class="flex h-8 items-center justify-center border border-[#FF4D4F] bg-white px-3 text-[#CF1322] transition-colors hover:bg-[#FFF1F0]"
            @click="handleCancel()"
          >
            Stop Run
          </button>
        </div>
      </header>

      <div class="flex-1 overflow-y-auto p-5">
        <div v-if="isBootstrapping" class="flex h-full items-center justify-center text-sm text-[#8C8C8C]">
          正在加载前后端状态...
        </div>

        <div
          v-else-if="!activeConversation"
          class="flex h-full items-center justify-center border border-dashed border-[#D9D9D9] bg-[#FAFAFA] text-sm text-[#8C8C8C]"
        >
          请选择会话，或直接新建一个会话开始执行。
        </div>

        <div
          v-else-if="!messages.length"
          class="flex h-full items-center justify-center border border-dashed border-[#D9D9D9] bg-[#FAFAFA] text-sm text-[#8C8C8C]"
        >
          当前会话还没有消息，发送问题后将通过 SSE 实时流式返回。
        </div>

        <div v-else class="space-y-7">
          <div v-for="message in messages" :key="message.id" class="flex flex-col">
            <div v-if="message.role === 'user'" class="ml-auto flex max-w-[85%] min-w-[240px] flex-col items-end">
              <div class="mb-1 text-[10px] uppercase tracking-[0.2em] text-[#1D39C4]">
                User · {{ formatTime(message.createdAt) }}
              </div>
              <div class="user-bubble border border-[#BFDBFE] bg-[#EFF6FF] px-4 py-3 text-sm text-[#1D39C4]">
                <div
                  v-for="(part, index) in textParts(message)"
                  :key="`${message.id}-user-${index}`"
                  class="markdown-body whitespace-pre-wrap leading-7"
                  v-html="renderMarkdown(String(part.text || ''))"
                ></div>
              </div>
            </div>

            <div v-else class="mr-auto w-full max-w-[90%]">
              <div class="mb-2 flex items-center justify-between border-b border-[#E8E8E8] pb-2 text-[10px] uppercase tracking-[0.2em] text-[#8C8C8C]">
                <span class="font-semibold text-[#389E0D]">Agent</span>
                <span>{{ formatTime(message.createdAt) }}</span>
              </div>

              <div v-if="thinkingParts(message).length" class="mb-4">
                <details class="group border border-[#E8E8E8] bg-[#FAFAFA]">
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
                        class="mb-3 flex items-center justify-between border border-[#D9D9D9] bg-white px-3 py-2 text-xs"
                      >
                        <div>
                          <div class="font-semibold text-[#1F1F1F]">{{ part.title || '执行步骤' }}</div>
                          <div class="mt-1 text-[#8C8C8C]">{{ part.stepId }}</div>
                        </div>
                        <span class="border border-[#D9D9D9] px-2 py-1 text-[#595959]">{{ part.status }}</span>
                      </div>

                      <div
                        v-else-if="isReasoningPart(part)"
                        class="mb-3 border-l-2 border-[#1677FF] bg-white px-3 py-2"
                      >
                        <div class="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#595959]">Reasoning</div>
                        <div class="text-sm leading-6 text-[#434343]">
                          {{ part.summary || part.content || '...' }}
                        </div>
                      </div>

                      <div
                        v-else-if="isToolCallPart(part)"
                        class="mb-3 border border-[#D9D9D9] bg-white p-3"
                      >
                        <div class="mb-3 flex items-center justify-between gap-3">
                          <div class="min-w-0">
                            <div class="truncate font-mono text-xs text-[#1F1F1F]">{{ part.toolName }}()</div>
                            <div class="mt-1 text-[11px] text-[#8C8C8C]">{{ part.id }}</div>
                          </div>
                          <span class="border px-2 py-1 text-[11px]" :class="toolStateClass(part.state)">
                            {{ part.state }}
                          </span>
                        </div>

                        <div class="grid gap-3 lg:grid-cols-2">
                          <div>
                            <div class="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8C8C8C]">Input</div>
                            <pre class="overflow-x-auto border border-[#E8E8E8] bg-[#FAFAFA] p-2 text-[11px] leading-5 text-[#434343]">{{ toolInputPreview(part) }}</pre>
                          </div>
                          <div>
                            <div class="mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#8C8C8C]">Output</div>
                            <pre class="overflow-x-auto border border-[#E8E8E8] bg-[#FAFAFA] p-2 text-[11px] leading-5 text-[#434343]">{{ toolOutputPreview(part) }}</pre>
                          </div>
                        </div>

                        <div class="mt-3">
                          <button class="border border-[#1677FF] bg-white px-3 py-1 text-xs text-[#1677FF] hover:bg-[#E6F4FF]" @click="inspectPart(part)">
                            Inspect in Sandbox →
                          </button>
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
                  class="markdown-body whitespace-pre-wrap text-sm leading-7 text-[#1F1F1F]"
                  v-html="renderMarkdown(String(part.text || ''))"
                ></div>
              </div>

              <div v-if="artifactCards(message).length" class="mt-4 space-y-2">
                <div
                  v-for="(part, index) in artifactCards(message)"
                  :key="`${message.id}-artifact-${index}`"
                  class="border border-[#D9D9D9] bg-[#FAFAFA] px-3 py-3"
                >
                  <div class="mb-2 flex items-center justify-between gap-3">
                    <div class="flex items-center gap-2">
                      <span class="border border-[#D9D9D9] bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-[#595959]">
                        {{ dataCardLabel(part) }}
                      </span>
                      <span class="text-sm font-medium text-[#1F1F1F]">{{ dataCardTitle(part) }}</span>
                    </div>
                    <button class="border border-[#1677FF] bg-white px-3 py-1 text-xs text-[#1677FF] hover:bg-[#E6F4FF]" @click="inspectPart(part)">
                      Inspect in Sandbox →
                    </button>
                  </div>
                  <div class="text-sm leading-6 text-[#595959]">
                    {{ part.summary || '结果已生成，可在右侧 Sandbox 查看完整内容。' }}
                  </div>
                </div>
              </div>

              <div
                v-if="!message.uiParts.length && message.status !== 'completed'"
                class="border border-dashed border-[#D9D9D9] bg-[#FAFAFA] px-3 py-3 text-sm text-[#8C8C8C]"
              >
                等待 Worker 产出事件流...
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="shrink-0 border-t border-[#D9D9D9] bg-[#FAFAFA] p-3">
        <div v-if="errorMessage" class="mb-3 flex items-center gap-2 border border-[#FFCCC7] bg-[#FFF2F0] px-3 py-2 text-sm text-[#CF1322]">
          <el-icon><Warning /></el-icon>
          <span>{{ errorMessage }}</span>
        </div>

        <div class="border border-[#D9D9D9] bg-white">
          <textarea
            v-model="composer"
            class="min-h-[120px] w-full resize-none border-0 bg-transparent p-3 text-sm leading-6 text-[#1F1F1F] outline-none placeholder:text-[#BFBFBF]"
            placeholder="输入 SQL、自然语言问题或执行指令..."
            @keydown.enter.exact.prevent="handleSend()"
          ></textarea>

          <div class="flex items-center justify-between border-t border-[#E8E8E8] bg-[#FAFAFA] px-3 py-2">
            <div class="text-xs text-[#8C8C8C]">Enter 发送，Shift + Enter 换行。当前执行依赖后端 API 与独立 Worker。</div>
            <button
              class="flex h-8 items-center justify-center border border-[#1677FF] bg-[#1677FF] px-4 text-sm text-white transition-colors hover:bg-[#4096FF] disabled:border-[#BFBFBF] disabled:bg-[#BFBFBF]"
              :disabled="isSending || !selectedSkillId"
              @click="handleSend()"
            >
              {{ isSending ? 'Submitting...' : 'Execute' }}
            </button>
          </div>
        </div>
      </div>
    </main>

    <aside class="flex w-[380px] shrink-0 flex-col bg-[#FAFAFA]">
      <div class="flex h-12 shrink-0 items-center justify-between border-b border-[#D9D9D9] px-4">
        <div class="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-[#595959]">
          <el-icon><DataBoard /></el-icon>
          Sandbox Inspector
        </div>
        <button
          v-if="selectedDetail"
          class="border border-[#D9D9D9] bg-white px-2 py-1 text-[11px] text-[#595959] hover:border-[#1677FF] hover:text-[#1677FF]"
          @click="clearSelectedDetail()"
        >
          Clear
        </button>
      </div>

      <div class="flex-1 overflow-y-auto bg-white p-4">
        <div
          v-if="!selectedDetail"
          class="flex h-full items-center justify-center border border-dashed border-[#D9D9D9] bg-[#FAFAFA] text-center text-sm text-[#8C8C8C]"
        >
          <div>
            <el-icon :size="24" class="mb-2"><Document /></el-icon>
            <p>右侧 Sandbox 为空。</p>
            <p class="mt-1 text-xs">点击任意 “Inspect in Sandbox →” 后，在这里查看完整 JSON、表格或图表。</p>
          </div>
        </div>

        <div
          v-else-if="selectedDetail.isLoading"
          class="flex h-full items-center justify-center border border-dashed border-[#D9D9D9] bg-[#FAFAFA] text-sm text-[#8C8C8C]"
        >
          正在加载 artifact 内容...
        </div>

        <div
          v-else-if="selectedDetail.error"
          class="border border-[#FFCCC7] bg-[#FFF2F0] px-3 py-3 text-sm text-[#CF1322]"
        >
          {{ selectedDetail.error }}
        </div>

        <div v-else class="space-y-4">
          <div class="border border-[#D9D9D9] bg-[#FAFAFA] px-3 py-3">
            <div class="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#595959]">Selection</div>
            <div class="text-sm font-medium text-[#1F1F1F]">
              {{ sandboxContent?.title || sandboxContent?.toolName || sandboxContent?.type || 'detail' }}
            </div>
            <div class="mt-2 space-y-1 text-xs text-[#8C8C8C]">
              <div>Type: {{ sandboxContent?.type }}</div>
              <div v-if="selectedDetail.artifact">Artifact ID: {{ selectedDetail.artifact.id }}</div>
              <div v-if="selectedDetail.artifact">Size: {{ selectedDetail.artifact.sizeBytes }} bytes</div>
              <div v-if="selectedDetail.artifact">Created: {{ formatDateTime(selectedDetail.artifact.createdAt) }}</div>
            </div>
          </div>

          <div v-if="sandboxContent && isDataChartPart(sandboxContent)" class="border border-[#D9D9D9] bg-[#FAFAFA] p-3">
            <div class="mb-3 text-sm font-medium text-[#1F1F1F]">{{ dataCardTitle(sandboxContent) }}</div>
            <VChart class="h-[320px] w-full bg-white" autoresize :option="chartOption(sandboxContent)" />
            <div v-if="sandboxContent.summary" class="mt-3 text-sm leading-6 text-[#595959]">
              {{ sandboxContent.summary }}
            </div>
          </div>

          <div v-else-if="sandboxContent && isDataTablePart(sandboxContent)" class="border border-[#D9D9D9] bg-[#FAFAFA] p-3">
            <div class="mb-3 text-sm font-medium text-[#1F1F1F]">{{ dataCardTitle(sandboxContent) }}</div>
            <el-table :data="tableRows(sandboxContent)" size="small" stripe row-key="__rowKey" style="width: 100%">
              <el-table-column
                v-for="column in tableColumns(sandboxContent)"
                :key="column"
                :prop="column"
                :label="column"
                min-width="120"
              />
            </el-table>
            <div v-if="sandboxContent.summary" class="mt-3 text-sm leading-6 text-[#595959]">
              {{ sandboxContent.summary }}
            </div>
          </div>

          <div v-else class="border border-[#D9D9D9] bg-[#FAFAFA] p-3">
            <div class="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-[#595959]">Raw Payload</div>
            <pre class="overflow-x-auto whitespace-pre-wrap break-all bg-white p-3 text-[12px] leading-5 text-[#434343]">{{ sandboxPayload() }}</pre>
          </div>
        </div>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.style-f-root * {
  box-shadow: none !important;
  border-radius: 0 !important;
}

.user-bubble {
  border-radius: 8px !important;
}

details > summary {
  list-style: none;
}

details > summary::-webkit-details-marker {
  display: none;
}

.markdown-body :deep(p) {
  margin: 0 0 0.75rem;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(pre) {
  overflow-x: auto;
  border: 1px solid #e8e8e8;
  background: #fafafa;
  padding: 12px;
}

.markdown-body :deep(code) {
  font-family:
    "IBM Plex Mono",
    "SFMono-Regular",
    Consolas,
    monospace;
  font-size: 0.92em;
}
</style>

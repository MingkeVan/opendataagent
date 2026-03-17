<script setup lang="ts">
import { Loading, RefreshLeft, Search, Warning } from '@element-plus/icons-vue'
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
  errorMessage,
  activeConversation,
  initialize,
  openConversation,
  createNewConversation,
  handleSend,
  renderMarkdown,
} = chat

const conversationSearch = ref('')

onMounted(async () => {
  await initialize()
})



function parseServerUtcIso(isoString: string) {
  if (!isoString) {
    return null
  }
  const normalized = /z|[+-]\d{2}:\d{2}$/i.test(isoString) ? isoString : `${isoString}Z`
  const parsed = new Date(normalized)
  return Number.isNaN(parsed.getTime()) ? null : parsed
}

function formatMonthDayTime(isoString: string) {
  const parsed = parseServerUtcIso(isoString)
  if (!parsed) return ''
  const m = parsed.getMonth() + 1
  const d = parsed.getDate()
  const h = String(parsed.getHours()).padStart(2, '0')
  const min = String(parsed.getMinutes()).padStart(2, '0')
  return `${m}月${d}日 ${h}:${min}`
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



function isPlaceholderConversationTitle(title?: string) {
  const normalized = String(title || '').trim()
  return !normalized || normalized === '新建会话'
}

function conversationListTitle(conversation: { title: string }) {
  return isPlaceholderConversationTitle(conversation.title) ? '未开始提问' : conversation.title
}



const filteredConversations = computed(() => {
  const keyword = conversationSearch.value.trim().toLowerCase()
  if (!keyword) {
    return conversations.value
  }
  return conversations.value.filter((conversation) => conversationListTitle(conversation).toLowerCase().includes(keyword))
})


</script>

<template>
  <div class="style-f-root flex h-screen min-w-[1100px] overflow-hidden bg-[#F4F5F7] font-['IBM_Plex_Sans','PingFang_SC','Hiragino_Sans_GB',sans-serif] text-[#1F1F1F]">
    
    <!-- Sidebar -->
    <aside class="sidebar-shell flex w-[260px] shrink-0 flex-col bg-white border-r border-[#E5EAF1]">
      <div class="px-5 py-5">
        <button
          class="flex h-[42px] w-full items-center justify-center rounded-lg bg-[#4F81FF] text-[15px] text-white transition-opacity hover:opacity-90 shadow-[0_2px_8px_rgba(79,129,255,0.25)] font-medium"
          @click="createNewConversation()"
        >
          新对话
        </button>
      </div>

      <div class="px-5 pb-3">
        <div class="hidden">
          <el-select v-model="selectedSkillId" :disabled="!skills.length">
            <el-option v-for="skill in skills" :key="skill.id" :value="skill.id" :label="`${skill.name} · ${skill.version}`"></el-option>
          </el-select>
        </div>

        <div class="relative mb-2">
          <el-icon class="pointer-events-none absolute left-[14px] top-1/2 -translate-y-1/2 text-[#98A2B3] text-[15px] font-bold"><Search /></el-icon>
          <input
            v-model="conversationSearch"
            class="h-[38px] w-full rounded-lg border border-[#E5EAF1] bg-white pl-[38px] pr-3 text-[14px] text-[#344054] outline-none transition-colors placeholder:text-[#BBBBBB] focus:border-[#4F81FF]"
            placeholder="搜索历史会话..."
          />
        </div>
      </div>

      <div class="flex-1 overflow-y-auto mt-1">
        <div v-if="!conversations.length && !isBootstrapping" class="px-5 py-5 text-[13px] text-[#8C8C8C]">还没有会话记录。</div>
        <div v-else-if="!filteredConversations.length" class="px-5 py-5 text-[13px] text-[#8C8C8C]">没有匹配的会话。</div>

        <button
          v-for="conversation in filteredConversations"
          :key="conversation.id"
          class="group w-full text-left transition-colors px-3 py-[2px]"
          @click="openConversation(conversation.id)"
        >
          <div 
            class="relative py-3 pl-3 pr-3 rounded-xl bg-transparent transition-colors duration-200"
            :class="activeConversationId === conversation.id ? 'bg-[#F4F7FF]' : 'hover:bg-[#F9FAFC]'"
          >
            <div class="flex items-start gap-2 mb-1.5">
              <el-icon class="text-[#86A8FF] mt-[2px] text-[16px]"><RefreshLeft /></el-icon>
              <div class="flex-1 truncate text-[14.5px] font-medium leading-[1.2]" :class="activeConversationId === conversation.id ? 'text-[#1F1F1F]' : 'text-[#595959]'">
                {{ conversationListTitle(conversation) }}
              </div>
            </div>
            <div class="pl-[26px] text-[12.5px] font-normal" :class="activeConversationId === conversation.id ? 'text-[#8C8C8C]' : 'text-[#A0AABF]'">
              {{ formatMonthDayTime(conversation.updatedAt) }}
            </div>
          </div>
        </button>
      </div>
    </aside>

    <!-- Main Chat Area -->
    <main class="main-shell flex min-w-0 flex-1 flex-col bg-[#F5F6F8]">
      <div class="flex-1 overflow-y-auto px-[40px] pt-8 pb-32 relative">
        <div v-if="isBootstrapping" class="flex h-full items-center justify-center text-[14px] text-[#8C8C8C]">正在加载前后端状态...</div>
        <div v-else-if="!activeConversation" class="empty-state mx-auto flex h-full max-w-[800px] items-center justify-center text-[14px] text-[#8C8C8C]">从左侧会话历史中继续。</div>

        <div v-else class="mx-auto w-full max-w-[860px] space-y-8">
          <div v-for="message in messages" :key="message.id" class="flex flex-col">
            
            <!-- User Bubble -->
            <div v-if="message.role === 'user'" class="ml-auto flex max-w-[82%] min-w-[240px] items-start justify-end gap-3">
              <div class="bg-[#4F81FF] px-5 py-[14px] text-[15.5px] text-white rounded-[16px] rounded-tr-[4px] shadow-[0_4px_16px_rgba(79,129,255,0.15)] leading-relaxed relative top-1">
                <div v-for="(part, index) in textParts(message)" :key="`${message.id}-user-${index}`" class="break-words font-normal">{{ part.text }}</div>
              </div>
              <div class="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[10px] bg-[#4F81FF] text-white text-[19px] shadow-[0_2px_10px_rgba(79,129,255,0.2)] mt-0.5" style="font-family: ui-sans-serif, system-ui; font-weight: 500;">m</div>
            </div>

            <!-- Agent Bubble -->
            <div v-else class="mr-auto w-full max-w-[860px]">
              <div class="bg-white rounded-[18px] p-6 shadow-[0_2px_24px_rgba(0,0,0,0.03)] border border-[#eff1f5]">
                
                <div v-for="(part, index) in textParts(message)" :key="`${message.id}-text-${index}`" class="mb-5 last:mb-0" v-show="index === 0">
                  <div class="markdown-body break-words text-[15px] leading-relaxed text-[#1F1F1F]" v-html="renderMarkdown(String(part.text || ''))"></div>
                </div>

                <div v-if="thinkingParts(message).length" class="mb-5 mt-2">
                  <details class="group bg-white rounded-xl">
                    <summary class="flex cursor-pointer items-center text-[14px] text-[#595959] select-none list-none w-max font-medium">
                      <span class="mr-1.5 tracking-wide">深度思考</span>
                      <svg class="h-3.5 w-3.5 transition-transform group-open:-rotate-180 text-[#8C8C8C]" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M19 9l-7 7-7-7" />
                      </svg>
                    </summary>

                    <div class="mt-4 border-l-[3px] border-[#eff1f5] pl-[18px] py-1 text-[13.5px] text-[#A0AABF] space-y-3.5 relative">
                      <template v-for="(part, index) in thinkingParts(message)" :key="`${message.id}-thinking-${index}`">
                        <div v-if="part.type === 'step'">{{ part.title || '执行步骤' }}</div>
                        <div v-else-if="isReasoningPart(part)" class="break-words leading-relaxed" v-html="renderMarkdown(String(part.summary || part.content || '...'))"></div>
                        <div v-else-if="isToolCallPart(part)" class="font-mono text-[12.5px] truncate text-[#8C8C8C]">调用工具：{{ part.toolName }}()</div>
                      </template>
                    </div>
                  </details>
                </div>
                
                <div v-for="(part, index) in textParts(message)" :key="`${message.id}-text-after-${index}`" class="mb-5 last:mb-0" v-show="index > 0">
                  <div class="markdown-body break-words text-[15px] leading-relaxed text-[#1F1F1F]" v-html="renderMarkdown(String(part.text || ''))"></div>
                </div>

                <div v-if="chartParts(message).length" class="mt-6 space-y-5">
                  <div v-for="(part, index) in chartParts(message)" :key="`${message.id}-chart-${index}`" class="w-full relative bg-[#F9FAFC] rounded-[14px] border border-[#EEF1F5] p-2">
                    <VChart class="h-[340px] w-full" autoresize :option="chartOption(part)" />
                  </div>
                </div>

                <div v-if="tableParts(message).length" class="mt-6 space-y-5">
                  <div v-for="(part, index) in tableParts(message)" :key="`${message.id}-table-${index}`" class="w-full overflow-x-auto rounded-[14px] border border-[#EEF1F5]">
                    <el-table :data="tableRows(part)" size="small" stripe style="width: 100%">
                      <el-table-column v-for="column in tableColumns(part)" :key="column" :prop="column" :label="column" min-width="120" />
                    </el-table>
                  </div>
                </div>
                
                <div v-if="artifactParts(message).length" class="mt-4 space-y-2">
                  <div v-for="(part, index) in artifactParts(message)" :key="`${message.id}-artifact-${index}`" class="rounded-xl border border-[#E1E7EF] bg-[#F7F9FF] px-4 py-3">
                    <div class="text-[14px] font-medium text-[#1F1F1F] mb-1">{{ dataCardTitle(part) }}</div>
                    <div class="text-[13px] text-[#595959] leading-relaxed">{{ part.summary || 'Artifact result generated.' }}</div>
                  </div>
                </div>

                <div v-if="!message.uiParts.length && message.status !== 'completed'" class="text-[14px] text-[#8C8C8C] flex items-center gap-2 mt-2">
                  <el-icon class="is-loading text-[#4F81FF]"><Loading /></el-icon> 正在思考中...
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Area -->
      <div class="absolute bottom-[28px] left-[300px] right-[40px] z-10 pointer-events-none">
        <div class="mx-auto w-full max-w-[860px] pointer-events-auto">
          <div v-if="errorMessage" class="mb-3 flex items-center gap-2 rounded-lg border border-[#FFCCC7] bg-[#FFF2F0] px-3 py-2 text-[14px] text-[#CF1322] shadow-sm">
            <el-icon><Warning /></el-icon> <span>{{ errorMessage }}</span>
          </div>

          <div class="relative rounded-[20px] border border-[#eff1f5] bg-white shadow-[0_4px_30px_rgba(0,0,0,0.06)] flex flex-col pt-4 pb-4 px-5 transition-shadow focus-within:shadow-[0_8px_40px_rgba(79,129,255,0.12)] focus-within:border-[#C0D3FF]">
            <textarea
              v-model="composer"
              class="min-h-[75px] w-full resize-none border-0 bg-transparent text-[15px] leading-relaxed text-[#1F1F1F] outline-none placeholder:text-[#BbC3D0] placeholder:font-normal"
              placeholder="请描述你的需求..."
              @keydown.enter.exact.prevent="handleSend()"
            ></textarea>

            <div class="flex items-center justify-between mt-2 border-t border-transparent pt-1">
              <div class="flex items-center gap-2.5 text-[#595959]">
                <button class="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-[#E5EAF1] transition-colors hover:bg-[#F4F5F7] text-[#595959] shadow-sm">
                  <svg class="h-[16px] w-[16px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                  </svg>
                </button>
                <button class="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-[#E5EAF1] transition-colors hover:bg-[#F4F5F7] text-[#595959] shadow-sm">
                  <svg class="h-[16px] w-[16px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                  </svg>
                </button>
                <button class="flex h-[34px] w-[34px] items-center justify-center rounded-[10px] border border-[#E5EAF1] transition-colors hover:bg-[#F4F5F7] text-[#595959] shadow-sm">
                  <svg class="h-[16px] w-[16px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.8">
                    <path stroke-linecap="round" stroke-linejoin="round" d="M21 12a9 9 0 01-9 9m9-9a9 9 0 00-9-9m9 9H3m9 9a9 9 0 01-9-9m9 9c1.657 0 3-4.03 3-9s-1.343-9-3-9m0 18c-1.657 0-3-4.03-3-9s1.343-9 3-9m-9 9a9 9 0 019-9" />
                  </svg>
                </button>
              </div>

              <button
                class="flex h-[36px] w-[36px] items-center justify-center rounded-full text-white transition-all duration-200 shrink-0"
                :class="(!!composer.trim() && !isSending && selectedSkillId) ? 'bg-[#8CAEFF] hover:bg-[#4F81FF] shadow-md' : 'bg-[#A2BFFF] cursor-not-allowed'"
                :disabled="isSending || !selectedSkillId"
                @click="handleSend()"
              >
                <el-icon v-if="isSending" class="is-loading"><Loading /></el-icon>
                <svg v-else class="h-[18px] w-[18px]" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 19V5m-7 7l7-7 7 7" />
                </svg>
              </button>
            </div>
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

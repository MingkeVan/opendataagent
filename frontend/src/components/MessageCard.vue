<script setup lang="ts">
import { computed } from 'vue'
import type { Message, UiPart } from '../types'
import ChartCard from './ChartCard.vue'

const props = defineProps<{
  message: Message
}>()

const emit = defineEmits<{
  selectDetail: [part: UiPart]
}>()

const timelineParts = computed(() =>
  props.message.uiParts.filter((part) => ['step', 'reasoning', 'tool-call', 'data-artifact'].includes(part.type)),
)

function tableRows(part: UiPart) {
  const columns = Array.isArray(part.columns) ? (part.columns as string[]) : []
  const rows = Array.isArray(part.rows) ? (part.rows as unknown[]) : []
  return rows.map((row) => {
    if (Array.isArray(row)) {
      return columns.reduce<Record<string, unknown>>((acc, column, index) => {
        acc[column] = row[index]
        return acc
      }, {})
    }
    return row as Record<string, unknown>
  })
}

function tableColumns(part: UiPart) {
  return Array.isArray(part.columns) ? (part.columns as string[]) : []
}

function chartOption(part: UiPart) {
  return (part.spec as Record<string, unknown>) || {}
}

function tagType(state?: unknown) {
  switch (state) {
    case 'failed':
      return 'danger'
    case 'output-ready':
      return 'success'
    case 'input-ready':
      return 'warning'
    default:
      return 'info'
  }
}
</script>

<template>
  <div
    class="rounded-[2rem] border px-5 py-4 shadow-panel"
    :class="
      message.role === 'user'
        ? 'ml-auto max-w-[70ch] border-emerald-300/70 bg-emerald-100/80'
        : 'mr-auto max-w-[78ch] border-white/70 bg-white/90'
    "
  >
    <div class="mb-4 flex items-center justify-between text-xs uppercase tracking-[0.22em] text-ink/50">
      <span>{{ message.role === 'user' ? 'User' : 'Agent' }}</span>
      <span>{{ new Date(message.createdAt).toLocaleTimeString() }}</span>
    </div>

    <div v-if="message.role === 'assistant' && timelineParts.length" class="mb-4 flex flex-wrap gap-2">
      <el-tag
        v-for="part in timelineParts"
        :key="`${part.type}-${part.id || part.stepId}`"
        effect="plain"
        round
      >
        {{
          part.type === 'step'
            ? part.title
            : part.type === 'reasoning'
              ? 'Reasoning'
              : part.type === 'tool-call'
                ? part.toolName
                : 'Artifact'
        }}
      </el-tag>
    </div>

    <div v-if="message.uiParts.length === 0 && message.status !== 'completed'" class="text-sm text-ink/60">
      正在准备响应...
    </div>

    <div class="space-y-4">
      <template v-for="(part, index) in message.uiParts" :key="`${part.type}-${part.id || part.stepId || index}`">
        <div
          v-if="part.type === 'text'"
          class="whitespace-pre-wrap text-[15px] leading-7 text-ink"
        >
          {{ part.text }}
        </div>

        <el-collapse v-else-if="part.type === 'reasoning'" class="reasoning-collapse">
          <el-collapse-item :name="part.id" :title="`Reasoning 摘要 · ${part.stepId || 'step'}`">
            <div class="rounded-2xl bg-stone-100/80 p-4 text-sm leading-6 text-ink/75">
              {{ part.summary }}
            </div>
          </el-collapse-item>
        </el-collapse>

        <div
          v-else-if="part.type === 'tool-call'"
          class="rounded-3xl border border-amber-200/70 bg-amber-50/80 p-4"
        >
          <div class="mb-3 flex items-center justify-between">
            <div>
              <div class="text-sm font-semibold text-ink">{{ part.toolName }}</div>
              <div class="text-xs text-ink/55">{{ part.id }}</div>
            </div>
            <el-tag round :type="tagType(part.state)">{{ part.state }}</el-tag>
          </div>
          <div class="grid gap-3 md:grid-cols-2">
            <div>
              <div class="mb-1 text-xs uppercase tracking-[0.18em] text-ink/40">Input</div>
              <pre class="overflow-auto rounded-2xl bg-white/80 p-3 text-xs text-ink/80">{{ JSON.stringify(part.input, null, 2) }}</pre>
            </div>
            <div>
              <div class="mb-1 text-xs uppercase tracking-[0.18em] text-ink/40">Output</div>
              <pre class="overflow-auto rounded-2xl bg-white/80 p-3 text-xs text-ink/80">{{ JSON.stringify(part.output, null, 2) }}</pre>
            </div>
          </div>
          <div class="mt-3 flex justify-end">
            <el-button size="small" text @click="emit('selectDetail', part)">查看详情</el-button>
          </div>
        </div>

        <ChartCard
          v-else-if="part.type === 'data-chart'"
          :title="String(part.title || '图表')"
          :option="chartOption(part)"
        />

        <div
          v-else-if="part.type === 'data-table'"
          class="overflow-hidden rounded-3xl border border-white/70 bg-white/80 p-4 shadow-panel"
        >
          <div class="mb-3 flex items-center justify-between">
            <div class="text-sm font-semibold text-ink">{{ part.title }}</div>
            <el-button size="small" text @click="emit('selectDetail', part)">展开</el-button>
          </div>
          <el-table :data="tableRows(part)" size="small" stripe style="width: 100%">
            <el-table-column
              v-for="column in tableColumns(part)"
              :key="column"
              :prop="column"
              :label="column"
              min-width="120"
            />
          </el-table>
          <div v-if="part.summary" class="mt-3 text-sm text-ink/65">{{ part.summary }}</div>
        </div>

        <div
          v-else-if="part.type === 'data-artifact'"
          class="rounded-3xl border border-sky-200/70 bg-sky-50/80 p-4"
        >
          <div class="mb-1 text-sm font-semibold text-ink">{{ part.title }}</div>
          <div class="mb-3 text-sm text-ink/65">{{ part.summary }}</div>
          <el-button size="small" type="primary" plain @click="emit('selectDetail', part)">打开 Artifact</el-button>
        </div>
      </template>
    </div>
  </div>
</template>

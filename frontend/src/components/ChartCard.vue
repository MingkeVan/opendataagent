<script setup lang="ts">
import { use } from 'echarts/core'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { BarChart, LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([GridComponent, TooltipComponent, LineChart, BarChart, CanvasRenderer])

defineProps<{
  option: Record<string, unknown>
  title?: string
}>()
</script>

<template>
  <div class="overflow-hidden rounded-3xl border border-white/70 bg-white/80 p-4 shadow-panel">
    <div v-if="title" class="mb-3 text-sm font-semibold text-ink/80">{{ title }}</div>
    <VChart autoresize class="h-72 w-full" :option="option" />
  </div>
</template>


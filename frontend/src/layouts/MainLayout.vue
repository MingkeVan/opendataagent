<script setup lang="ts">
import { Plus, RefreshRight, Loading, DataBoard } from '@element-plus/icons-vue'
import { onMounted } from 'vue'
import { useChat } from '../composables/useChat'

const chat = useChat()
const {
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
  activeConversation,
  apiBase,
  loadSkills,
  loadConversations,
  openConversation,
  createNewConversation,
  handleSend,
  handleCancel,
  renderMarkdown
} = chat

onMounted(async () => {
  await loadSkills()
  await loadConversations(true)
})

function formatTime(isoString: string) {
  if (!isoString) return ''
  const d = new Date(isoString)
  return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}
</script>

<template>
  <div class="flex h-screen w-full flex-col overflow-hidden bg-[#FAFAFA] text-[#333333] font-sans antialiased style-f-root">
    <!-- Top Nav / Toolbar -->
    <header class="flex h-12 shrink-0 items-center justify-between border-b border-[#E0E0E0] bg-[#FAFAFA] px-4">
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <div class="h-4 w-4 rounded-sm bg-[#1677FF]"></div>
          <span class="text-sm font-semibold tracking-wide text-[#333333]">DataAgent Studio</span>
          <span class="rounded bg-[#E6F4FF] px-1.5 py-0.5 text-[10px] font-bold text-[#1677FF]">HYBRID VIEW</span>
        </div>
        <div class="h-4 w-px bg-[#D9D9D9]"></div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-[#666666]">Skill:</span>
          <select 
            v-model="selectedSkillId" 
            class="h-7 cursor-pointer border border-[#D9D9D9] bg-white px-2 py-0.5 text-xs text-[#333333] outline-none hover:border-[#1677FF] focus:border-[#1677FF]"
          >
            <option v-for="skill in skills" :key="skill.id" :value="skill.id">
              {{ skill.name }} ({{ skill.version }})
            </option>
          </select>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-[#666666]">API:</span>
          <span class="text-xs font-mono text-[#333333]">{{ apiBase }}</span>
        </div>
      </div>
      
      <div class="flex items-center gap-3">
        <div v-if="activeRunId" class="flex items-center gap-2 rounded border border-[#1677FF] bg-[#E6F4FF] px-2 py-1 text-xs text-[#1677FF]">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>{{ runStatus }}</span>
        </div>
        <div v-else class="flex items-center gap-2 px-2 py-1 text-xs text-[#666666]">
          Status: {{ runStatus }}
        </div>
        
        <button 
          v-if="activeRunId"
          @click="handleCancel()" 
          class="flex h-7 items-center justify-center border border-[#FF4D4F] bg-white px-3 text-xs text-[#FF4D4F] transition-colors hover:bg-[#FFF1F0] active:bg-[#FFCCC7]"
        >
          Stop Run
        </button>
      </div>
    </header>

    <div class="flex flex-1 overflow-hidden">
      <!-- Left Panel: Explorer / Conversations -->
      <aside class="flex w-64 shrink-0 flex-col border-r border-[#E0E0E0] bg-[#FAFAFA]">
        <div class="flex shrink-0 items-center justify-between border-b border-[#E0E0E0] p-2">
          <span class="text-xs font-semibold uppercase text-[#666666]">Explorer</span>
          <div class="flex gap-1">
            <button class="flex h-6 w-6 items-center justify-center text-[#666666] hover:bg-[#EBEBEB]" title="Refresh" @click="loadConversations()">
              <el-icon :size="14"><RefreshRight /></el-icon>
            </button>
            <button class="flex h-6 w-6 items-center justify-center text-[#666666] hover:bg-[#EBEBEB]" title="New Conversation" @click="createNewConversation()">
              <el-icon :size="14"><Plus /></el-icon>
            </button>
          </div>
        </div>
        <div class="flex-1 overflow-y-auto p-1">
          <button
            v-for="c in conversations"
            :key="c.id"
            class="flex w-full items-center gap-2 px-2 py-1.5 text-left text-xs transition-colors"
            :class="[
              activeConversationId === c.id 
                ? 'bg-[#E6F4FF] text-[#1677FF] border-l-2 border-[#1677FF]' 
                : 'text-[#333333] hover:bg-[#EBEBEB] border-l-2 border-transparent'
            ]"
            @click="openConversation(c.id)"
          >
            <span class="truncate pl-1">{{ c.title }}</span>
          </button>
        </div>
      </aside>

      <!-- Main Editor / Conversation Area -->
      <main class="flex flex-1 flex-col bg-white border-r border-[#E0E0E0]">
        <!-- Message Stream (Terminal like) -->
        <div class="flex-1 overflow-y-auto p-4 text-sm">
          <div v-if="!activeConversation" class="flex h-full items-center justify-center text-[#999999]">
            Select or create a conversation to begin.
          </div>
          
          <div v-for="msg in messages" :key="msg.id" class="mb-6 flex flex-col">
            <!-- User Message -->
            <div v-if="msg.role === 'user'" class="self-end max-w-[85%] min-w-[200px] flex flex-col items-end">
              <div class="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-wider text-[#1E3A8A] opacity-70">
                <span>{{ formatTime(msg.createdAt) }}</span>
                <span class="font-bold">USER</span>
              </div>
              
              <div v-for="(part, idx) in msg.uiParts.filter((p: any) => p.type === 'text')" :key="`txt-${msg.id}-${idx}`" class="mb-2 last:mb-0 text-[#1E3A8A] rounded bg-[#EFF6FF] border border-[#BFDBFE] px-4 py-2.5 !rounded-lg" style="border-radius: 8px !important;">
                <div class="markdown-body whitespace-pre-wrap leading-relaxed" v-html="renderMarkdown(String((part as any).text))"></div>
              </div>
            </div>

            <!-- Agent Message -->
            <div v-else class="self-start max-w-[90%] w-full">
              <div class="mb-2 flex items-center gap-2 border-b border-[#E0E0E0] pb-1 text-[10px] uppercase tracking-wider">
                <span class="font-bold text-[#52C41A]">AGENT</span>
                <span class="text-[#999999]">{{ formatTime(msg.createdAt) }}</span>
              </div>
              
              <div class="py-1">
                <!-- Group non-text parts (reasoning, tool calls) into a single details block -->
                <details 
                  v-if="msg.uiParts.some((p: any) => p.type !== 'text')" 
                  class="group mb-3"
                >
                  <!-- Hide default marker using list-none and webkit pseudo class -->
                  <summary class="cursor-pointer select-none text-xs text-[#999999] hover:text-[#666666] list-none [&::-webkit-details-marker]:hidden">
                    <span class="mr-1 inline-block transition-transform group-open:rotate-90">▶</span> 
                    Thinking Process 
                    <span v-if="msg.uiParts.reduce((acc: number, p: any) => acc + (p.durationMs || 0), 0) > 0">
                      ({{ msg.uiParts.reduce((acc: number, p: any) => acc + (p.durationMs || 0), 0) }}ms)
                    </span>
                  </summary>
                  
                  <div class="mt-2 ml-1 border-l-2 border-[#E0E0E0] pl-3 py-1 space-y-3">
                    <template v-for="(part, idx) in msg.uiParts" :key="idx">
                      
                      <!-- Reasoning -->
                      <div v-if="part.type === 'reasoning'">
                        <div class="text-[11px] font-bold text-[#999999] mb-1">Reasoning: {{ part.summary }}</div>
                        <div class="text-[11px] text-[#666666] whitespace-pre-wrap leading-normal">{{ part.content || '...' }}</div>
                      </div>
                      
                      <!-- Tool Call -->
                      <div v-else-if="part.type === 'tool_call'" class="rounded-sm border border-[#E0E0E0] bg-[#FAFAFA] p-2 font-mono text-[11px]">
                        <div class="flex items-center justify-between mb-1">
                          <span class="font-bold text-[#333333]">> {{ part.toolName }}()</span>
                          <span class="text-[#999999]">
                            {{ part.status }} 
                            <span v-if="part.durationMs">({{ part.durationMs }}ms)</span>
                          </span>
                        </div>
                        <div class="truncate text-[#666666] opacity-80 max-w-full">
                          Input: {{ JSON.stringify(part.input) }}
                        </div>
                        <div class="mt-1.5 flex gap-2">
                          <button class="text-[#1677FF] hover:underline" @click="selectedDetail = part">Inspect in Sandbox →</button>
                        </div>
                      </div>

                    </template>
                  </div>
                </details>

                <!-- Render Text parts normally -->
                <div v-for="(part, idx) in msg.uiParts.filter((p: any) => p.type === 'text')" :key="`txt-${msg.id}-${idx}`" class="mb-3 last:mb-0">
                  <div class="markdown-body whitespace-pre-wrap leading-relaxed" v-html="renderMarkdown(String((part as any).text))">
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Input Area (Editor like) -->
        <div class="shrink-0 border-t border-[#E0E0E0] bg-[#FAFAFA] p-2">
          <div class="relative flex min-h-[120px] flex-col rounded border border-[#D9D9D9] bg-white focus-within:border-[#1677FF]">
            <textarea
              v-model="composer"
              class="flex-1 resize-none bg-transparent p-3 text-sm text-[#333333] outline-none placeholder:text-[#BFBFBF]"
              placeholder="Enter SQL/Command or natural language query..."
              @keydown.enter.exact.prevent="handleSend()"
            ></textarea>
            <div class="flex shrink-0 items-center justify-between border-t border-[#F0F0F0] bg-[#FAFAFA] px-3 py-2">
              <span class="text-[10px] text-[#999999]">Press Enter to execute</span>
              <button 
                @click="handleSend()" 
                :disabled="isSending"
                class="flex h-7 items-center justify-center bg-[#1677FF] px-4 text-xs tracking-wide text-white transition-colors hover:bg-[#4096FF] focus:outline-none disabled:bg-[#B3D8FF] disabled:cursor-not-allowed"
              >
                Execute
              </button>
            </div>
          </div>
        </div>
      </main>
      
      <!-- Right Panel: Persistent Sandbox Dashboard (from Style D) -->
      <aside class="flex w-[35%] min-w-[350px] shrink-0 flex-col bg-[#FAFAFA]">
        <div class="flex h-10 shrink-0 items-center justify-between border-b border-[#E0E0E0] px-4 text-xs font-semibold uppercase text-[#666666]">
          <div class="flex items-center gap-2">
            <el-icon><DataBoard /></el-icon>
            Sandbox Inspector
          </div>
          <span v-if="selectedDetail" class="font-mono text-[#1677FF]">Viewing: {{ selectedDetail.type }}</span>
        </div>
        
        <div class="flex-1 overflow-auto p-4 bg-white">
          <div v-if="!selectedDetail" class="flex h-full items-center justify-center text-sm text-[#999999] text-center border-2 border-dashed border-[#E0E0E0] bg-[#FAFAFA]">
            <div>
              <el-icon :size="24" class="mb-2"><DataBoard /></el-icon>
              <p>Sandbox is empty.</p>
              <p class="mt-1 font-normal text-xs px-8">Click "Inspect in Sandbox →" on any action artifact to inspect it here.</p>
            </div>
          </div>
          
          <div v-else class="h-full border border-[#E0E0E0] bg-[#FAFAFA] p-4 font-mono text-xs text-[#333333]">
            <pre class="overflow-x-auto">{{ JSON.stringify(selectedDetail, null, 2) }}</pre>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
/* Force border radius logic to be zeroed out in this root element */
.style-f-root * {
  border-radius: 0px !important;
}

/* Exception for the active light blue background button if needed, but 0px preferred */
button, input, select, textarea {
  border-radius: 0px !important;
}

/* Hide default details marker robustly */
details > summary {
  list-style: none;
}
details > summary::-webkit-details-marker {
  display: none;
}
</style>

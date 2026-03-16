import type { StreamEvent, UiPart } from '../types'

type StreamPart = StreamEvent & { type: string }

function upsertPart(parts: UiPart[], match: (part: UiPart) => boolean, create: () => UiPart) {
  const existing = parts.find(match)
  if (existing) {
    return existing
  }
  const next = create()
  parts.push(next)
  return next
}

export function getStreamPart(event: StreamEvent): StreamPart | null {
  if (event.kind === 'part' && event.payload && typeof event.payload === 'object') {
    return {
      seq: Number(event.seq || 0),
      ...(event.payload as Record<string, unknown>),
    } as StreamPart
  }
  if (event.type) {
    return event as StreamPart
  }
  return null
}

export function applyStreamEvent(parts: UiPart[], event: StreamEvent): UiPart[] {
  const streamPart = getStreamPart(event)
  const next = parts.map((part) => ({ ...part }))
  if (!streamPart) {
    return next
  }

  switch (streamPart.type) {
    case 'start-step': {
      upsertPart(
        next,
        (part) => part.type === 'step' && part.stepId === streamPart.stepId,
        () => ({
          type: 'step',
          stepId: streamPart.stepId as string,
          title: (streamPart.title as string) || '执行步骤',
          status: 'running',
        }),
      )
      break
    }
    case 'finish-step': {
      const step = upsertPart(
        next,
        (part) => part.type === 'step' && part.stepId === streamPart.stepId,
        () => ({
          type: 'step',
          stepId: streamPart.stepId as string,
          title: (streamPart.title as string) || '执行步骤',
          status: 'completed',
        }),
      )
      step.status = 'completed'
      break
    }
    case 'reasoning-start': {
      upsertPart(
        next,
        (part) => part.type === 'reasoning' && part.id === streamPart.id,
        () => ({
          type: 'reasoning',
          id: streamPart.id as string,
          stepId: streamPart.stepId as string | undefined,
          summary: '',
        }),
      )
      break
    }
    case 'reasoning-delta': {
      const reasoningPart = upsertPart(
        next,
        (part) => part.type === 'reasoning' && part.id === streamPart.id,
        () => ({
          type: 'reasoning',
          id: streamPart.id as string,
          stepId: streamPart.stepId as string | undefined,
          summary: '',
        }),
      )
      reasoningPart.summary = `${String(reasoningPart.summary || '')}${String(streamPart.delta || '')}`
      break
    }
    case 'text-start': {
      upsertPart(
        next,
        (part) => part.type === 'text' && part.id === streamPart.id,
        () => ({
          type: 'text',
          id: streamPart.id as string,
          stepId: streamPart.stepId as string | undefined,
          text: '',
        }),
      )
      break
    }
    case 'text-delta': {
      const textPart = upsertPart(
        next,
        (part) => part.type === 'text' && part.id === streamPart.id,
        () => ({
          type: 'text',
          id: streamPart.id as string,
          stepId: streamPart.stepId as string | undefined,
          text: '',
        }),
      )
      textPart.text = `${String(textPart.text || '')}${String(streamPart.delta || '')}`
      break
    }
    case 'tool-input-start': {
      upsertPart(
        next,
        (part) => part.type === 'tool-call' && part.id === streamPart.toolCallId,
        () => ({
          type: 'tool-call',
          id: streamPart.toolCallId as string,
          toolName: String(streamPart.toolName || 'tool'),
          state: 'input-streaming',
          stepId: streamPart.stepId as string | undefined,
          input: null,
          output: null,
          inputText: '',
        }),
      )
      break
    }
    case 'tool-input-delta': {
      const toolPart = upsertPart(
        next,
        (part) => part.type === 'tool-call' && part.id === streamPart.toolCallId,
        () => ({
          type: 'tool-call',
          id: streamPart.toolCallId as string,
          toolName: String(streamPart.toolName || 'tool'),
          state: 'input-streaming',
          stepId: streamPart.stepId as string | undefined,
          input: null,
          output: null,
          inputText: '',
        }),
      )
      toolPart.inputText = `${String(toolPart.inputText || '')}${String(streamPart.delta || '')}`
      toolPart.state = 'input-streaming'
      break
    }
    case 'tool-input-available': {
      const toolPart = upsertPart(
        next,
        (part) => part.type === 'tool-call' && part.id === streamPart.toolCallId,
        () => ({
          type: 'tool-call',
          id: streamPart.toolCallId as string,
          toolName: String(streamPart.toolName || 'tool'),
          state: 'input-ready',
          stepId: streamPart.stepId as string | undefined,
          input: null,
          output: null,
          inputText: '',
        }),
      )
      toolPart.input = streamPart.input
      toolPart.state = 'input-ready'
      break
    }
    case 'tool-output-available': {
      const toolPart = upsertPart(
        next,
        (part) => part.type === 'tool-call' && part.id === streamPart.toolCallId,
        () => ({
          type: 'tool-call',
          id: streamPart.toolCallId as string,
          toolName: String(streamPart.toolName || 'tool'),
          state: 'running',
          stepId: streamPart.stepId as string | undefined,
          input: null,
          output: null,
          inputText: '',
        }),
      )
      toolPart.output = streamPart.output
      toolPart.state = 'output-ready'
      break
    }
    case 'tool-failed': {
      const toolPart = upsertPart(
        next,
        (part) => part.type === 'tool-call' && part.id === streamPart.toolCallId,
        () => ({
          type: 'tool-call',
          id: streamPart.toolCallId as string,
          toolName: String(streamPart.toolName || 'tool'),
          state: 'failed',
          stepId: streamPart.stepId as string | undefined,
          input: null,
          output: null,
          inputText: '',
        }),
      )
      toolPart.state = 'failed'
      toolPart.error = String(streamPart.error || 'tool failed')
      break
    }
    case 'data-chart':
    case 'data-table':
    case 'data-artifact': {
      const exists = next.some((part) => part.type === streamPart.type && part.id === streamPart.id)
      if (!exists) {
        next.push({ ...streamPart })
      }
      break
    }
    default:
      break
  }

  return next
}

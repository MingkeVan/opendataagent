import type { StreamEvent, UiPart } from '../types'

function upsertPart(parts: UiPart[], match: (part: UiPart) => boolean, create: () => UiPart) {
  const existing = parts.find(match)
  if (existing) {
    return existing
  }
  const next = create()
  parts.push(next)
  return next
}

export function applyStreamEvent(parts: UiPart[], event: StreamEvent): UiPart[] {
  const next = parts.map((part) => ({ ...part }))

  switch (event.type) {
    case 'start-step': {
      upsertPart(
        next,
        (part) => part.type === 'step' && part.stepId === event.stepId,
        () => ({
          type: 'step',
          stepId: event.stepId as string,
          title: (event.title as string) || '执行步骤',
          status: 'running',
        }),
      )
      break
    }
    case 'finish-step': {
      const step = upsertPart(
        next,
        (part) => part.type === 'step' && part.stepId === event.stepId,
        () => ({
          type: 'step',
          stepId: event.stepId as string,
          title: (event.title as string) || '执行步骤',
          status: 'completed',
        }),
      )
      step.status = 'completed'
      break
    }
    case 'reasoning-start': {
      upsertPart(
        next,
        (part) => part.type === 'reasoning' && part.id === event.id,
        () => ({
          type: 'reasoning',
          id: event.id as string,
          stepId: event.stepId as string | undefined,
          summary: '',
        }),
      )
      break
    }
    case 'reasoning-delta': {
      const part = upsertPart(
        next,
        (item) => item.type === 'reasoning' && item.id === event.id,
        () => ({
          type: 'reasoning',
          id: event.id as string,
          stepId: event.stepId as string | undefined,
          summary: '',
        }),
      )
      part.summary = `${String(part.summary || '')}${String(event.delta || '')}`
      break
    }
    case 'text-start': {
      upsertPart(
        next,
        (part) => part.type === 'text' && part.id === event.id,
        () => ({
          type: 'text',
          id: event.id as string,
          stepId: event.stepId as string | undefined,
          text: '',
        }),
      )
      break
    }
    case 'text-delta': {
      const part = upsertPart(
        next,
        (item) => item.type === 'text' && item.id === event.id,
        () => ({
          type: 'text',
          id: event.id as string,
          stepId: event.stepId as string | undefined,
          text: '',
        }),
      )
      part.text = `${String(part.text || '')}${String(event.delta || '')}`
      break
    }
    case 'tool-input-start': {
      upsertPart(
        next,
        (part) => part.type === 'tool-call' && part.id === event.toolCallId,
        () => ({
          type: 'tool-call',
          id: event.toolCallId as string,
          toolName: event.toolName,
          state: 'input-streaming',
          stepId: event.stepId as string | undefined,
          input: null,
          output: null,
        }),
      )
      break
    }
    case 'tool-input-available': {
      const part = upsertPart(
        next,
        (item) => item.type === 'tool-call' && item.id === event.toolCallId,
        () => ({
          type: 'tool-call',
          id: event.toolCallId as string,
          toolName: event.toolName,
          state: 'input-ready',
          stepId: event.stepId as string | undefined,
          input: null,
          output: null,
        }),
      )
      part.input = event.input
      part.state = 'input-ready'
      break
    }
    case 'tool-output-available': {
      const part = upsertPart(
        next,
        (item) => item.type === 'tool-call' && item.id === event.toolCallId,
        () => ({
          type: 'tool-call',
          id: event.toolCallId as string,
          toolName: event.toolName,
          state: 'running',
          stepId: event.stepId as string | undefined,
          input: null,
          output: null,
        }),
      )
      part.output = event.output
      part.state = 'output-ready'
      break
    }
    case 'tool-failed': {
      const part = upsertPart(
        next,
        (item) => item.type === 'tool-call' && item.id === event.toolCallId,
        () => ({
          type: 'tool-call',
          id: event.toolCallId as string,
          toolName: event.toolName,
          state: 'failed',
          stepId: event.stepId as string | undefined,
          input: null,
          output: null,
        }),
      )
      part.state = 'failed'
      part.error = event.error
      break
    }
    case 'data-chart':
    case 'data-table':
    case 'data-artifact': {
      const exists = next.some((part) => part.type === event.type && part.id === event.id)
      if (!exists) {
        next.push({ ...event })
      }
      break
    }
    default:
      break
  }

  return next
}


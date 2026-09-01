<template>
  <span class="hint-icon">
    <button
      ref="buttonEl"
      type="button"
      class="hint-icon__button"
      :aria-label="label"
      :aria-expanded="open"
      @mouseenter="show"
      @mouseleave="hide"
      @focus="show"
      @blur="hide"
      @click.stop="toggle"
    >
      ?
    </button>
    <Teleport to="body">
      <span
        v-if="open && position"
        class="hint-icon__bubble"
        role="tooltip"
        :style="{ left: `${position.x}px`, top: `${position.y}px` }"
      >
        <slot>{{ text }}</slot>
      </span>
    </Teleport>
  </span>
</template>

<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'

/**
 * Collapses a block of explanatory copy into a small marker next to its
 * heading. The guidance stays one hover away for someone meeting a screen for
 * the first time, and stops taking up room once they know their way around.
 */
withDefaults(
  defineProps<{
    /** Tooltip copy; a default slot may be used instead for richer content. */
    text?: string
    label?: string
  }>(),
  { text: '', label: '查看说明' },
)

const BUBBLE_WIDTH = 268
const buttonEl = ref<HTMLElement | null>(null)
const open = ref(false)
// Positioned in the viewport rather than next to the marker so the bubble is
// never clipped by the scrolling panels these hints sit in.
const position = ref<{ x: number; y: number } | null>(null)

function place(): void {
  const rect = buttonEl.value?.getBoundingClientRect()
  if (!rect) return
  const x = Math.min(
    Math.max(8, rect.left + rect.width / 2 - BUBBLE_WIDTH / 2),
    window.innerWidth - BUBBLE_WIDTH - 8,
  )
  position.value = { x, y: rect.bottom + 8 }
}

function show(): void {
  place()
  open.value = true
}

function hide(): void {
  open.value = false
}

function toggle(): void {
  if (open.value) hide()
  else show()
}

onBeforeUnmount(hide)
</script>

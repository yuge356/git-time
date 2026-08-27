<template>
  <svg
    v-if="paths.length > 0"
    class="tree-connectors"
    :style="svgStyle"
    aria-hidden="true"
  >
    <path
      v-for="path in paths"
      :key="path.id"
      :d="path.d"
      fill="none"
      :stroke="lineColor"
      stroke-width="2"
      stroke-linecap="round"
    />
  </svg>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

defineOptions({ name: 'TreeConnectors' })

const props = defineProps<{
  /** The parent node's .task-row element. */
  parentEl: HTMLElement | null
  /** The child nodes' .task-row elements. */
  childrenEls: HTMLElement[]
  /** Color for the connector lines. */
  color?: string
}>()

const lineColor = computed(() => props.color || 'var(--mindmap-line, #a797e8)')

interface ConnectorPath {
  id: string
  d: string
}

const containerRect = ref<DOMRect | null>(null)
const parentRect = ref<DOMRect | null>(null)
const childrenRects = ref<DOMRect[]>([])
const branchEl = ref<HTMLElement | null>(null)

const svgStyle = computed(() => ({
  position: 'absolute' as const,
  top: '0',
  left: '0',
  width: '100%',
  height: '100%',
  pointerEvents: 'none' as const,
  overflow: 'visible' as const,
  zIndex: 1,
}))

const paths = computed<ConnectorPath[]>(() => {
  if (!parentRect.value || !containerRect.value || childrenRects.value.length === 0) return []

  const container = containerRect.value
  const parent = parentRect.value
  const branch = branchEl.value

  // Calculate scale factor (in case canvas has CSS transform zoom)
  const scaleX = branch && branch.offsetWidth > 0 ? container.width / branch.offsetWidth : 1
  const scaleY = branch && branch.offsetHeight > 0 ? container.height / branch.offsetHeight : 1

  // Parent's right-center point relative to container in local unscaled coordinates
  const parentRightX = (parent.right - container.left) / scaleX
  const parentCenterY = (parent.top + parent.height / 2 - container.top) / scaleY

  return childrenRects.value.map((child, index) => {
    // Child's left-center point relative to container in local unscaled coordinates
    const childLeftX = (child.left - container.left) / scaleX
    const childCenterY = (child.top + child.height / 2 - container.top) / scaleY

    // Cubic bezier control points — midX creates a smooth S-curve
    const midX = (parentRightX + childLeftX) / 2

    const d = [
      `M ${parentRightX} ${parentCenterY}`,
      `C ${midX} ${parentCenterY}, ${midX} ${childCenterY}, ${childLeftX} ${childCenterY}`,
    ].join(' ')

    return { id: `connector-${index}`, d }
  })
})

function measure(): void {
  const parent = props.parentEl
  if (!parent) return

  // Find the branch container (the .task-mind-branch element)
  const branch = parent.closest('.task-mind-branch') as HTMLElement | null
  if (!branch) return
  branchEl.value = branch

  containerRect.value = branch.getBoundingClientRect()
  parentRect.value = parent.getBoundingClientRect()
  childrenRects.value = props.childrenEls
    .filter((el) => el != null && el.isConnected)
    .map((el) => el.getBoundingClientRect())
}

let resizeObserver: ResizeObserver | null = null
let animFrameId = 0

function scheduleMeasure(): void {
  if (animFrameId) cancelAnimationFrame(animFrameId)
  animFrameId = requestAnimationFrame(measure)
}

onMounted(() => {
  scheduleMeasure()
  window.addEventListener('resize', scheduleMeasure)
  const branch = props.parentEl?.closest('.task-mind-branch') as HTMLElement | null
  if (branch) {
    resizeObserver = new ResizeObserver(scheduleMeasure)
    resizeObserver.observe(branch)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  window.removeEventListener('resize', scheduleMeasure)
  if (animFrameId) cancelAnimationFrame(animFrameId)
})

watch(
  () => [props.parentEl, props.childrenEls, props.childrenEls.length],
  () => {
    resizeObserver?.disconnect()
    scheduleMeasure()
    const branch = props.parentEl?.closest('.task-mind-branch') as HTMLElement | null
    if (branch) {
      resizeObserver = new ResizeObserver(scheduleMeasure)
      resizeObserver.observe(branch)
    }
  },
  { deep: true, flush: 'post' },
)
</script>

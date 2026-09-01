import type { TaskBudgetMode, TaskRepeatRule } from './task'

/** One module or task inside a template outline. */
export interface TemplateNode {
  node_type: 'MODULE' | 'TASK'
  title: string
  estimated_seconds: number
  children: TemplateNode[]
}

export interface ProjectTemplate {
  id: string
  owner_id: string
  name: string
  description: string | null
  icon: string | null
  /** Set when this template started as a copy of a built-in preset. */
  preset_key: string | null
  budget_mode: TaskBudgetMode
  fixed_budget_seconds: number | null
  default_estimated_seconds: number | null
  default_repeat_rule: TaskRepeatRule | null
  structure: TemplateNode[]
  sort_order: number
  created_at: string
  updated_at: string
}

export interface ProjectTemplatePayload {
  id?: string
  name: string
  description: string | null
  icon: string | null
  preset_key?: string | null
  budget_mode: TaskBudgetMode
  fixed_budget_seconds: number | null
  default_estimated_seconds: number | null
  default_repeat_rule: TaskRepeatRule | null
  structure: TemplateNode[]
}

/**
 * A template as the projects page renders it. Built-in presets and saved
 * templates share one shape so the picker can list them together; only a
 * saved template carries an `id`.
 */
export interface TemplateOption {
  key: string
  id: string | null
  name: string
  description: string
  icon: string
  budget_mode: TaskBudgetMode
  fixed_budget_seconds: number | null
  default_estimated_seconds: number | null
  default_repeat_rule: TaskRepeatRule | null
  structure: TemplateNode[]
  /** True for the shipped presets, which have no server row until edited. */
  isPreset: boolean
}

function node(
  title: string,
  minutes = 0,
  children: TemplateNode[] = [],
): TemplateNode {
  return {
    node_type: children.length > 0 ? 'MODULE' : 'TASK',
    title,
    estimated_seconds: children.length > 0 ? 0 : minutes * 60,
    children,
  }
}

/**
 * Shipped starting points. They exist only in the client until the user edits
 * one, at which point the edited copy is saved as a normal template that keeps
 * the preset's key and replaces it in the picker.
 */
export const BUILT_IN_TEMPLATES: TemplateOption[] = [
  {
    key: 'study',
    id: null,
    name: '学习课程',
    description: '预习、听课、复习、练习四段式，适合一门课或一本教材。',
    icon: '📚',
    budget_mode: 'ROLLUP',
    fixed_budget_seconds: null,
    default_estimated_seconds: 45 * 60,
    default_repeat_rule: null,
    isPreset: true,
    structure: [
      node('预习', 0, [node('通读教材章节', 30), node('整理疑问清单', 15)]),
      node('听课与笔记', 0, [node('课堂笔记整理', 30)]),
      node('复习', 0, [node('重点回顾', 30), node('错题复盘', 30)]),
      node('练习', 0, [node('课后习题', 45)]),
    ],
  },
  {
    key: 'project',
    id: null,
    name: '项目推进',
    description: '调研、设计、实施、复盘四个阶段，适合一次交付。',
    icon: '🚀',
    budget_mode: 'ROLLUP',
    fixed_budget_seconds: null,
    default_estimated_seconds: 60 * 60,
    default_repeat_rule: null,
    isPreset: true,
    structure: [
      node('调研', 0, [node('明确目标与范围', 60), node('收集资料', 60)]),
      node('设计', 0, [node('拟定方案', 90)]),
      node('实施', 0, [node('第一阶段执行', 120), node('第二阶段执行', 120)]),
      node('复盘', 0, [node('总结与归档', 45)]),
    ],
  },
  {
    key: 'exam',
    id: null,
    name: '考试备考',
    description: '按知识点过一轮、刷题、模考、查漏补缺。',
    icon: '📝',
    budget_mode: 'ROLLUP',
    fixed_budget_seconds: null,
    default_estimated_seconds: 60 * 60,
    default_repeat_rule: null,
    isPreset: true,
    structure: [
      node('知识点梳理', 0, [node('通览考纲', 45), node('整理知识框架', 60)]),
      node('专项练习', 0, [node('章节题库', 60), node('错题整理', 45)]),
      node('模拟考试', 0, [node('全真模考', 120), node('模考订正', 60)]),
      node('考前冲刺', 0, [node('高频考点回顾', 60)]),
    ],
  },
  {
    key: 'reading',
    id: null,
    name: '读书计划',
    description: '拆成若干次阅读加一次读书笔记。',
    icon: '📖',
    budget_mode: 'ROLLUP',
    fixed_budget_seconds: null,
    default_estimated_seconds: 30 * 60,
    default_repeat_rule: 'DAILY',
    isPreset: true,
    structure: [
      node('每日阅读', 30),
      node('章节摘要', 20),
      node('读书笔记', 45),
    ],
  },
  {
    key: 'habit',
    id: null,
    name: '习惯养成',
    description: '一项每天重复的小任务，配合连续打卡。',
    icon: '🌱',
    budget_mode: 'ROLLUP',
    fixed_budget_seconds: null,
    default_estimated_seconds: 20 * 60,
    default_repeat_rule: 'DAILY',
    isPreset: true,
    structure: [node('每日练习', 20)],
  },
]

export function countTemplateNodes(nodes: TemplateNode[]): { modules: number; tasks: number } {
  let modules = 0
  let tasks = 0
  const walk = (items: TemplateNode[]): void => {
    for (const item of items) {
      if (item.node_type === 'MODULE') modules += 1
      else tasks += 1
      walk(item.children)
    }
  }
  walk(nodes)
  return { modules, tasks }
}

export function templateTotalSeconds(nodes: TemplateNode[]): number {
  return nodes.reduce(
    (total, item) => total + item.estimated_seconds + templateTotalSeconds(item.children),
    0,
  )
}

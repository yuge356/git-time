import { createApp, h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'

import GanttChart from '@/components/GanttChart.vue'
import type { GanttChartRow, TaskDailyPoint } from '@/types/analytics'
import type { TaskStatus } from '@/types/task'
import '@/styles/main.css'

const MS_DAY = 86_400_000
const today = new Date().toISOString().slice(0, 10)
const todayMs = Date.parse(`${today}T00:00:00Z`)

function day(offset: number): string {
  return new Date(todayMs + offset * MS_DAY).toISOString().slice(0, 10)
}

function daysFrom(offsets: number[], seconds = 1_800): TaskDailyPoint[] {
  return offsets.map((offset) => ({ date: day(offset), seconds }))
}

const rows: GanttChartRow[] = [
  {
    id: 'task-reading',
    title: '考研英语 / 阅读真题精读训练（2010—2024 年全部篇章逐句精读）',
    totalSeconds: 24 * 3_600,
    firstDate: day(-21),
    lastDate: day(-2),
    days: daysFrom([-21, -20, -19, -18, -17, -14, -13, -12, -9, -8, -5, -4, -3, -2], 1_800),
    projectId: 'proj-english-9f2a',
    projectTitle: '考研英语',
    status: 'IN_PROGRESS' as TaskStatus,
    progressRatio: 0.65,
    activeDays: 14,
    spanDays: 20,
    plannedStart: day(-24),
    plannedEnd: day(2),
  },
  {
    id: 'task-vocab',
    title: '考研英语 / 恋练有词单词打卡',
    totalSeconds: 6 * 3_600,
    firstDate: day(-9),
    lastDate: day(0),
    days: daysFrom([-9, -8, -7, -5, -4, -3, -1, 0], 2_700),
    projectId: 'proj-english-9f2a',
    projectTitle: '考研英语',
    status: 'DONE' as TaskStatus,
    progressRatio: 1,
    activeDays: 8,
    spanDays: 10,
    plannedStart: day(-10),
    plannedEnd: day(0),
  },
  {
    id: 'task-linear',
    title: '机器学习基础 / 线性代数复习',
    totalSeconds: 12 * 3_600,
    firstDate: day(-30),
    lastDate: day(-1),
    days: daysFrom([-30, -29, -28, -27, -26, -25, -24, -23, -22, -21], 1_200),
    projectId: 'proj-ml-4c81',
    projectTitle: '机器学习基础',
    status: 'IN_PROGRESS' as TaskStatus,
    progressRatio: 0.3,
    activeDays: 10,
    spanDays: 30,
    plannedStart: day(-32),
    plannedEnd: day(-2),
  },
  {
    id: 'task-course',
    title: '机器学习基础 / 吴恩达深度学习课程',
    totalSeconds: 4 * 3_600,
    firstDate: day(-6),
    lastDate: day(0),
    days: daysFrom([-6, -4, -2, 0], 3_600),
    projectId: 'proj-ml-4c81',
    projectTitle: '机器学习基础',
    status: 'TODO' as TaskStatus,
    progressRatio: null,
    activeDays: 4,
    spanDays: 7,
    plannedStart: day(-1),
    plannedEnd: day(9),
  },
  {
    id: 'task-legacy',
    title: '已删除项目的归档任务',
    totalSeconds: 2 * 3_600,
    firstDate: day(-40),
    lastDate: day(-38),
    days: daysFrom([-40, -39, -38], 2_400),
    projectId: null,
    projectTitle: '未关联项目',
    status: null,
    progressRatio: null,
    activeDays: 3,
    spanDays: 3,
    plannedStart: null,
    plannedEnd: null,
  },
]

const router = createRouter({
  history: createMemoryHistory(),
  routes: [{ path: '/:pathMatch(.*)*', component: { template: '<div />' } }],
})

const app = createApp({
  setup() {
    return () =>
      h('main', { style: 'max-width: 1240px; margin: 0 auto; padding: 28px 24px;' }, [
        h('p', {
          style:
            'margin: 0 0 14px; padding: 8px 14px; border: 1px solid rgba(124,92,252,0.2); border-radius: 12px; background: rgba(124,92,252,0.06); color: #5b3ec8; font-size: 12px;',
        }, '预览说明：这是今日页「计划进度表」组件的独立预览，使用模拟数据；正式入口在「今天」页面专注计时下方。可切换 天 / 周 / 月，悬浮条形查看详情，点击条形、按住拖拽平移时间轴。'),
        h(GanttChart, { rows, today, loading: false, error: '' }),
      ])
  },
})

app.use(router)
app.mount('#app')

/**
 * Project Color Identity System.
 * Generates stable, deterministic theme color suites for projects based on their unique ID.
 */

export interface ProjectTheme {
  name: string
  primary: string
  primaryHover: string
  soft: string
  softHover: string
  line: string
  border: string
  moduleBar: string
  taskBar: string
  glow: string
  text: string
}

export const PROJECT_THEMES: ProjectTheme[] = [
  {
    name: 'violet',
    primary: '#7c5cfc',
    primaryHover: '#6845f5',
    soft: 'rgba(124, 92, 252, 0.08)',
    softHover: 'rgba(124, 92, 252, 0.14)',
    line: 'rgba(124, 92, 252, 0.22)',
    border: 'rgba(124, 92, 252, 0.18)',
    moduleBar: '#8e73f4',
    taskBar: '#b8a8f8',
    glow: 'rgba(124, 92, 252, 0.20)',
    text: '#5b3ec8',
  },
  {
    name: 'blue',
    primary: '#2563eb',
    primaryHover: '#1d4ed8',
    soft: 'rgba(37, 99, 235, 0.08)',
    softHover: 'rgba(37, 99, 235, 0.14)',
    line: 'rgba(37, 99, 235, 0.22)',
    border: 'rgba(37, 99, 235, 0.18)',
    moduleBar: '#3b82f6',
    taskBar: '#93c5fd',
    glow: 'rgba(37, 99, 235, 0.20)',
    text: '#1e40af',
  },
  {
    name: 'teal',
    primary: '#0d9488',
    primaryHover: '#0f766e',
    soft: 'rgba(13, 148, 136, 0.08)',
    softHover: 'rgba(13, 148, 136, 0.14)',
    line: 'rgba(13, 148, 136, 0.22)',
    border: 'rgba(13, 148, 136, 0.18)',
    moduleBar: '#14b8a6',
    taskBar: '#5eead4',
    glow: 'rgba(13, 148, 136, 0.20)',
    text: '#115e59',
  },
  {
    name: 'amber',
    primary: '#d97706',
    primaryHover: '#b45309',
    soft: 'rgba(217, 119, 6, 0.08)',
    softHover: 'rgba(217, 119, 6, 0.14)',
    line: 'rgba(217, 119, 6, 0.22)',
    border: 'rgba(217, 119, 6, 0.18)',
    moduleBar: '#f59e0b',
    taskBar: '#fcd34d',
    glow: 'rgba(217, 119, 6, 0.20)',
    text: '#92400e',
  },
  {
    name: 'rose',
    primary: '#e11d48',
    primaryHover: '#be123c',
    soft: 'rgba(225, 29, 72, 0.08)',
    softHover: 'rgba(225, 29, 72, 0.14)',
    line: 'rgba(225, 29, 72, 0.22)',
    border: 'rgba(225, 29, 72, 0.18)',
    moduleBar: '#f43f5e',
    taskBar: '#fda4af',
    glow: 'rgba(225, 29, 72, 0.20)',
    text: '#9f1239',
  },
  {
    name: 'emerald',
    primary: '#059669',
    primaryHover: '#047857',
    soft: 'rgba(5, 150, 105, 0.08)',
    softHover: 'rgba(5, 150, 105, 0.14)',
    line: 'rgba(5, 150, 105, 0.22)',
    border: 'rgba(5, 150, 105, 0.18)',
    moduleBar: '#10b981',
    taskBar: '#6ee7b7',
    glow: 'rgba(5, 150, 105, 0.20)',
    text: '#065f46',
  },
  {
    name: 'indigo',
    primary: '#4f46e5',
    primaryHover: '#4338ca',
    soft: 'rgba(79, 70, 229, 0.08)',
    softHover: 'rgba(79, 70, 229, 0.14)',
    line: 'rgba(79, 70, 229, 0.22)',
    border: 'rgba(79, 70, 229, 0.18)',
    moduleBar: '#6366f1',
    taskBar: '#a5b4fc',
    glow: 'rgba(79, 70, 229, 0.20)',
    text: '#3730a3',
  },
  {
    name: 'cyan',
    primary: '#0284c7',
    primaryHover: '#0369a1',
    soft: 'rgba(2, 132, 199, 0.08)',
    softHover: 'rgba(2, 132, 199, 0.14)',
    line: 'rgba(2, 132, 199, 0.22)',
    border: 'rgba(2, 132, 199, 0.18)',
    moduleBar: '#0ea5e9',
    taskBar: '#7dd3fc',
    glow: 'rgba(2, 132, 199, 0.20)',
    text: '#075985',
  },
]

/**
 * Deterministically returns a project's theme palette based on its UUID or ID string.
 * The output is permanently consistent across sessions and view mode changes.
 */
export function getProjectTheme(projectId?: string | null): ProjectTheme {
  const fallback = PROJECT_THEMES[0] as ProjectTheme
  if (!projectId) return fallback
  let hash = 0
  for (let i = 0; i < projectId.length; i++) {
    hash = (hash * 31 + projectId.charCodeAt(i)) | 0
  }
  const index = Math.abs(hash) % PROJECT_THEMES.length
  return PROJECT_THEMES[index] ?? fallback
}

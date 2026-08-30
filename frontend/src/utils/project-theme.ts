/**
 * Project Color Identity System.
 * Generates stable, deterministic theme color suites for projects based on their unique ID.
 * All palettes stay inside DayFlow's violet family (hue ~234-273) so every project reads as
 * part of the brand's purple language while remaining distinguishable by depth and tint.
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
    name: 'grape',
    primary: '#6d28d9',
    primaryHover: '#5b21b6',
    soft: 'rgba(109, 40, 217, 0.08)',
    softHover: 'rgba(109, 40, 217, 0.14)',
    line: 'rgba(109, 40, 217, 0.22)',
    border: 'rgba(109, 40, 217, 0.18)',
    moduleBar: '#8347e3',
    taskBar: '#c0a4f0',
    glow: 'rgba(109, 40, 217, 0.20)',
    text: '#4c1d95',
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
    name: 'purple',
    primary: '#9333ea',
    primaryHover: '#7e22ce',
    soft: 'rgba(147, 51, 234, 0.08)',
    softHover: 'rgba(147, 51, 234, 0.14)',
    line: 'rgba(147, 51, 234, 0.22)',
    border: 'rgba(147, 51, 234, 0.18)',
    moduleBar: '#a553ec',
    taskBar: '#d0a5f7',
    glow: 'rgba(147, 51, 234, 0.20)',
    text: '#6b21a8',
  },
  {
    name: 'lavender',
    primary: '#a78bfa',
    primaryHover: '#8f6cf9',
    soft: 'rgba(167, 139, 250, 0.08)',
    softHover: 'rgba(167, 139, 250, 0.14)',
    line: 'rgba(167, 139, 250, 0.22)',
    border: 'rgba(167, 139, 250, 0.18)',
    moduleBar: '#b39dfb',
    taskBar: '#d9cdfd',
    glow: 'rgba(167, 139, 250, 0.20)',
    text: '#6d4ad4',
  },
  {
    name: 'plum',
    primary: '#5b21b6',
    primaryHover: '#4c1d95',
    soft: 'rgba(91, 33, 182, 0.08)',
    softHover: 'rgba(91, 33, 182, 0.14)',
    line: 'rgba(91, 33, 182, 0.22)',
    border: 'rgba(91, 33, 182, 0.18)',
    moduleBar: '#7439d4',
    taskBar: '#b69af2',
    glow: 'rgba(91, 33, 182, 0.20)',
    text: '#3b1580',
  },
  {
    name: 'periwinkle',
    primary: '#818cf8',
    primaryHover: '#6366f1',
    soft: 'rgba(129, 140, 248, 0.08)',
    softHover: 'rgba(129, 140, 248, 0.14)',
    line: 'rgba(129, 140, 248, 0.22)',
    border: 'rgba(129, 140, 248, 0.18)',
    moduleBar: '#97a1fa',
    taskBar: '#c7cffd',
    glow: 'rgba(129, 140, 248, 0.20)',
    text: '#4f46e5',
  },
  {
    name: 'orchid',
    primary: '#c084fc',
    primaryHover: '#a855f7',
    soft: 'rgba(192, 132, 252, 0.08)',
    softHover: 'rgba(192, 132, 252, 0.14)',
    line: 'rgba(192, 132, 252, 0.22)',
    border: 'rgba(192, 132, 252, 0.18)',
    moduleBar: '#cf9cfd',
    taskBar: '#e9d5fe',
    glow: 'rgba(192, 132, 252, 0.20)',
    text: '#9333ea',
  },
]

/**
 * Deterministically returns a project's theme palette based on its UUID or ID string.
 * The output is permanently consistent across sessions, pages and view mode changes.
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

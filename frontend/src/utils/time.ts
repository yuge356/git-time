export function formatDuration(totalSeconds: number): string {
  if (totalSeconds <= 0) return '未设置'

  const totalMinutes = Math.round(totalSeconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours > 0 && minutes > 0) return `${hours} 小时 ${minutes} 分钟`
  if (hours > 0) return `${hours} 小时`
  return `${minutes} 分钟`
}

/** Compact variant for tight summary chips (e.g. "2小时50分"). */
export function formatDurationCompact(totalSeconds: number): string {
  if (totalSeconds <= 0) return '0 分钟'

  const totalMinutes = Math.round(totalSeconds / 60)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours > 0 && minutes > 0) return `${hours}时${minutes}分`
  if (hours > 0) return `${hours}小时`
  return `${minutes}分钟`
}


import type { SessionSnapshot } from '@/types/session'

export function snapshotDuration(
  snapshot: SessionSnapshot,
  now = new Date(),
): number {
  if (snapshot.status !== 'RUNNING' || !snapshot.last_resumed_at) {
    return snapshot.duration_seconds
  }
  const elapsed = Math.max(
    0,
    Math.floor((now.getTime() - new Date(snapshot.last_resumed_at).getTime()) / 1000),
  )
  return snapshot.duration_seconds + elapsed
}

export function formatTimer(totalSeconds: number): string {
  const safeSeconds = Math.max(0, Math.floor(totalSeconds))
  const hours = Math.floor(safeSeconds / 3600)
  const minutes = Math.floor((safeSeconds % 3600) / 60)
  const seconds = safeSeconds % 60
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':')
}


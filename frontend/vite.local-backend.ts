import { spawn, spawnSync, type ChildProcess } from 'node:child_process'
import { existsSync } from 'node:fs'
import { connect } from 'node:net'
import { fileURLToPath, URL } from 'node:url'

import type { Plugin, ViteDevServer } from 'vite'

const backendDirectory = fileURLToPath(new URL('../backend/', import.meta.url))
const pythonExecutable = fileURLToPath(
  new URL('../backend/.venv/Scripts/python.exe', import.meta.url),
)
const backendHealthUrl = 'http://127.0.0.1:8000/health'

async function backendIsHealthy(): Promise<boolean> {
  try {
    const response = await fetch(backendHealthUrl, {
      signal: AbortSignal.timeout(1200),
    })
    if (!response.ok) return false
    const body = (await response.json()) as { status?: string; database?: string }
    return body.status === 'ok' && body.database === 'ok'
  } catch {
    return false
  }
}

function backendPortIsOccupied(): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = connect({ host: '127.0.0.1', port: 8000 })
    socket.setTimeout(500)
    socket.once('connect', () => {
      socket.destroy()
      resolve(true)
    })
    const finish = () => {
      socket.destroy()
      resolve(false)
    }
    socket.once('error', finish)
    socket.once('timeout', finish)
  })
}

export function localBackendPlugin(): Plugin {
  let backendProcess: ChildProcess | null = null
  let healthTimer: ReturnType<typeof setInterval> | null = null
  let starting = false
  let disposed = false
  let warnedAboutPort = false

  async function ensureBackend(server: ViteDevServer): Promise<void> {
    if (disposed || starting || (backendProcess && backendProcess.exitCode === null)) return

    if (await backendIsHealthy()) {
      warnedAboutPort = false
      return
    }

    if (await backendPortIsOccupied()) {
      if (!warnedAboutPort) {
        server.config.logger.warn(
          '[local backend] Port 8000 is occupied, but its health check failed.',
        )
        warnedAboutPort = true
      }
      return
    }

    if (!existsSync(pythonExecutable)) {
      server.config.logger.error(
        `[local backend] Python environment is missing: ${pythonExecutable}`,
      )
      return
    }

    starting = true
    warnedAboutPort = false
    server.config.logger.info('[local backend] Starting database migration and API service...')

    const migration = spawnSync(
      pythonExecutable,
      ['-m', 'alembic', 'upgrade', 'head'],
      {
        cwd: backendDirectory,
        env: process.env,
        stdio: 'inherit',
        windowsHide: true,
      },
    )

    if (migration.status !== 0) {
      server.config.logger.error('[local backend] Database migration failed; API was not started.')
      starting = false
      return
    }

    backendProcess = spawn(
      pythonExecutable,
      ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8000'],
      {
        cwd: backendDirectory,
        env: { ...process.env, PYTHONUNBUFFERED: '1' },
        stdio: 'inherit',
        windowsHide: true,
      },
    )
    starting = false

    backendProcess.once('spawn', () => {
      server.config.logger.info('[local backend] API service is running on http://127.0.0.1:8000')
    })
    backendProcess.once('exit', (code, signal) => {
      backendProcess = null
      if (!disposed) {
        server.config.logger.warn(
          `[local backend] API service stopped (${signal ?? code ?? 'unknown'}); it will be restarted.`,
        )
      }
    })
    backendProcess.once('error', (error) => {
      backendProcess = null
      server.config.logger.error(`[local backend] Failed to start: ${error.message}`)
    })
  }

  return {
    name: 'time-budget-local-backend',
    apply: 'serve',
    async configureServer(server) {
      await ensureBackend(server)
      healthTimer = setInterval(() => {
        void ensureBackend(server)
      }, 3000)

      server.httpServer?.once('close', () => {
        disposed = true
        if (healthTimer) clearInterval(healthTimer)
        if (backendProcess?.exitCode === null) backendProcess.kill()
      })
    },
  }
}

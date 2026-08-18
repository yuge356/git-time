import { spawn } from 'node:child_process'
import { connect } from 'node:net'

const previewUrl = 'http://127.0.0.1:5174'

async function previewIsHealthy() {
  try {
    const response = await fetch(`${previewUrl}/health`, {
      signal: AbortSignal.timeout(1_500),
    })
    if (!response.ok) return false
    const body = await response.json()
    return body.status === 'ok' && body.database === 'ok'
  } catch {
    return false
  }
}

function portIsOccupied() {
  return new Promise((resolve) => {
    const socket = connect({ host: '127.0.0.1', port: 5174 })
    socket.setTimeout(800)
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

if (await previewIsHealthy()) {
  console.log(`Local preview is already running: ${previewUrl}`)
  process.exit(0)
}

if (await portIsOccupied()) {
  console.error(
    'Port 5174 is in use, but it is not a healthy project preview. Stop the process using that port, then run this command again.',
  )
  process.exit(1)
}

const child = spawn('corepack', ['pnpm', '--dir', 'frontend', 'dev'], {
  stdio: 'inherit',
})

child.once('error', (error) => {
  console.error(`Unable to start the local preview: ${error.message}`)
  process.exit(1)
})
child.once('exit', (code, signal) => {
  process.exitCode = code ?? (signal ? 1 : 0)
})

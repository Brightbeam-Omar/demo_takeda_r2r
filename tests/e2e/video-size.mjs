// Prints the pixel size and length of a recorded video (`make record-video` shows it; F14-AC-10 checks it).
// It asks the browser itself, so no ffprobe is needed. Usage: node video-size.mjs ../../artifacts/video/run-of-show.webm
import { chromium } from '@playwright/test'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const file = resolve(process.argv[2] ?? '../../artifacts/video/run-of-show.webm')
const bytes = readFileSync(file)
const browser = await chromium.launch()
const page = await browser.newPage()
const info = await page.evaluate(async (base64) => {
  const url = URL.createObjectURL(new Blob([Uint8Array.from(atob(base64), (c) => c.charCodeAt(0))], { type: 'video/webm' }))
  const video = document.createElement('video')
  video.muted = true
  video.src = url
  await new Promise((done, fail) => {
    video.onloadedmetadata = done
    video.onerror = () => fail(new Error('the browser cannot play this file'))
  })
  if (!Number.isFinite(video.duration)) {
    // A live webm has no duration in its header until it is seeked to the end.
    video.currentTime = 1e9
    await new Promise((done) => (video.onseeked = video.ontimeupdate = done))
  }
  return { width: video.videoWidth, height: video.videoHeight, seconds: video.duration }
}, bytes.toString('base64'))
await browser.close()
console.log(`${file}: ${info.width}x${info.height}, ${Math.round(info.seconds)} s`)
if (info.width !== 1440 || info.height !== 900) process.exit(1)

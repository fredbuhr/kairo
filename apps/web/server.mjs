// Serve only the built SPA. No development server, shell, directory listing or runtime dependency.
import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { resolve, extname, sep } from 'node:path'
const root = resolve('dist')
const types = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon', '.woff2': 'font/woff2' }
const server = createServer(async (req, res) => {
  res.setHeader('X-Content-Type-Options', 'nosniff')
  res.setHeader('X-Frame-Options', 'DENY')
  res.setHeader('Referrer-Policy', 'same-origin')
  if (!['GET', 'HEAD'].includes(req.method)) { res.writeHead(405); res.end(); return }
  try {
    const path = decodeURIComponent(new URL(req.url, 'http://localhost').pathname)
    let file = resolve(root, '.' + path)
    if (!file.startsWith(root + sep) || path.includes('\0')) file = resolve(root, 'index.html')
    try { if (!(await stat(file)).isFile()) file = resolve(root, 'index.html') }
    catch { if (extname(path)) { res.writeHead(404); res.end(); return }; file = resolve(root, 'index.html') }
    const body = await readFile(file)
    res.setHeader('Content-Type', types[extname(file)] || 'application/octet-stream')
    res.setHeader('Cache-Control', extname(file) === '.html' ? 'no-store' : 'public, max-age=3600')
    res.setHeader('Content-Length', body.length)
    res.writeHead(200); res.end(req.method === 'HEAD' ? undefined : body)
  } catch { res.writeHead(400); res.end() }
})
server.requestTimeout = 15000
server.headersTimeout = 10000
server.listen(5173, '0.0.0.0')
for (const signal of ['SIGTERM', 'SIGINT']) process.on(signal, () => { server.close(); server.closeIdleConnections() })

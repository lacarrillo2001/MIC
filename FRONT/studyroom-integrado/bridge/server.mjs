import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { timingSafeEqual } from 'node:crypto';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { fileURLToPath } from 'node:url';
import { BackendClient, ApiError } from './backend-client.mjs';
import { SessionLink } from './session-link.mjs';

const root = fileURLToPath(new URL('../', import.meta.url));
const defaults = { brightness: 1.25, lightingPreset: 'neutro', musicStyle: 'ambiental', volume: 42, focusMinutes: 25, sessionActive: false, sessionStartedAt: null };
const routeRules = {
  usuarios: /^\/(auth\/(login|registro)|usuarios\/me(\/retiro)?|perfiles\/me|tonos\/configuracion|evaluaciones-tonos(\/[a-f\d]{24})?)$/,
  catalogo: /^\/(catalogo\/(canciones|artistas|generos)|recomendaciones(\/[a-f\d]{24})?|feedback(\/[a-f\d]{24}\/reintentar)?|youtube\/(configuracion|feedback|voz|recomendaciones(\/[a-f\d]{24}\/(resolver|reproduccion|feedback|voz))?))$/,
  sesiones: /^\/(sesiones(\/[a-f\d]{24}(\/(vinculacion|estado|eventos|encuesta))?)?|encuestas\/configuracion|audios\/[a-f\d]{24}\/contenido|descargas(\/[a-f\d]{24}(\/contenido)?)?)$/,
};
async function body(req) {
  let size = 0; const chunks = [];
  for await (const chunk of req) { size += chunk.length; if (size > 65536) throw new ApiError(413, 'Solicitud demasiado grande'); chunks.push(chunk); }
  try { return JSON.parse(Buffer.concat(chunks).toString() || '{}'); } catch { throw new ApiError(400, 'JSON inválido'); }
}
function bearer(req) { const value = req.headers.authorization || ''; if (!value.startsWith('Bearer ')) throw new ApiError(401, 'Iniciar sesión'); return value.slice(7); }
function roomAuth(req, key) {
  const actual = Buffer.from(req.headers['x-room-key'] || ''); const expected = Buffer.from(key);
  if (actual.length !== expected.length || !timingSafeEqual(actual, expected)) throw new ApiError(403, 'Sala no autorizada');
}
function validateCommand(data) {
  if (!data || typeof data.id !== 'string' || !/^[\w-]{8,100}$/.test(data.id) || !['activa', 'pausada', 'finalizada', 'interrumpida'].includes(data.estado)) throw new ApiError(422, 'Comando inválido');
}

export function createBridge(options = {}) {
  const mode = options.mode || process.env.MODE || 'local';
  if (!['local', 'integrado'].includes(mode)) throw new Error('MODE debe ser local o integrado');
  const roomKey = options.roomKey || process.env.ROOM_KEY || '';
  if (mode === 'integrado' && (roomKey.length < 32 || roomKey.startsWith('GENERAR'))) throw new Error('Ejecutar npm run setup para configurar la clave de sala');
  const client = options.client || new BackendClient({ usuarios: process.env.USUARIOS_URL || 'http://127.0.0.1:8001', catalogo: process.env.CATALOGO_URL || 'http://127.0.0.1:8002', sesiones: process.env.SESIONES_URL || 'http://127.0.0.1:8003' });
  const link = new SessionLink(client);
  const file = options.stateFile || path.join(root, 'bridge/runtime-state.json');
  let state = { ...defaults }, seen = 0;
  if (mode === 'local') {
    try { const stored = JSON.parse(fs.readFileSync(file, 'utf8')); for (const key of ['brightness', 'lightingPreset', 'musicStyle', 'volume', 'focusMinutes']) if (Object.hasOwn(stored, key)) state[key] = stored[key]; } catch {}
  }
  const allowed = new Set((options.origins || process.env.ALLOWED_ORIGINS || 'http://localhost:5174,http://127.0.0.1:5174,http://localhost:8788,http://127.0.0.1:8788').split(','));
  function json(res, status, data, origin) {
    res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff',
      ...(origin ? { 'Access-Control-Allow-Origin': origin, Vary: 'Origin' } : {}) }); res.end(JSON.stringify(data));
  }
  function view(snapshot = {}) {
    if (mode === 'local' && state.sessionActive && Date.now() - Date.parse(state.sessionStartedAt) >= state.focusMinutes * 60000) state.sessionActive = false;
    return { ...state, ...(snapshot.sceneSettings || {}), mode, vrConnected: seen > 0 && Date.now() - seen < 6500,
      ...(mode === 'integrado' ? { ...snapshot, sessionActive: snapshot.estado === 'activa', sessionStartedAt: snapshot.sessionStartedAt || null } : {}) };
  }
  const server = http.createServer(async (req, res) => {
    const origin = req.headers.origin;
    try {
      if (origin && !allowed.has(origin)) throw new ApiError(403, 'Origen no autorizado');
      if (req.method === 'OPTIONS') { res.writeHead(204, { ...(origin ? { 'Access-Control-Allow-Origin': origin } : {}), 'Access-Control-Allow-Headers': 'Authorization,Content-Type,Range', 'Access-Control-Allow-Methods': 'GET,POST,PUT,PATCH,OPTIONS' }); return res.end(); }
      const url = new URL(req.url, 'http://localhost');
      if (req.method === 'GET' && url.pathname === '/api/config') return json(res, 200, { mode, oneRoom: true }, origin);
      if (req.method === 'GET' && url.pathname === '/api/health') return json(res, 200, { ok: true, service: 'studyroom-bridge', mode }, origin);
      if (url.pathname.startsWith('/backend/')) {
        if (mode !== 'integrado') throw new ApiError(409, 'Backend desactivado en modo local');
        const [, , service, ...rest] = url.pathname.split('/'); const apiPath = '/' + rest.join('/');
        if (!routeRules[service]?.test(apiPath) || !['GET', 'POST', 'PUT'].includes(req.method)) throw new ApiError(404, 'Ruta no publicada');
        const token = req.headers.authorization?.startsWith('Bearer ') ? req.headers.authorization.slice(7) : undefined;
        const response = await client.raw(service, apiPath + url.search, { method: req.method, token, body: req.method === 'GET' ? undefined : await body(req), range: req.headers.range });
        const headers = { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...(origin ? { 'Access-Control-Allow-Origin': origin } : {}) };
        for (const key of ['content-type', 'content-length', 'content-range', 'accept-ranges']) if (response.headers.has(key)) headers[key] = response.headers.get(key);
        res.writeHead(response.status, headers);
        if (response.body) await pipeline(Readable.fromWeb(response.body), res); else res.end();
        return;
      }
      if (req.method === 'GET' && url.pathname === '/api/state') {
        return json(res, 200, view(mode === 'integrado' ? await link.refresh(bearer(req)) : {}), origin);
      }
      if (req.method === 'PATCH' && url.pathname === '/api/state') {
        if (mode === 'integrado') await link.owner(bearer(req));
        const data = await body(req); const next = { ...state };
        if (!data || typeof data !== 'object' || Array.isArray(data)) throw new ApiError(400, 'Objeto JSON requerido');
        for (const [key, value] of Object.entries(data)) {
          if (mode === 'integrado' && !['brightness', 'lightingPreset', 'volume'].includes(key)) throw new ApiError(409, 'La sesión y las preferencias musicales pertenecen al backend');
          if (key === 'brightness' && Number.isFinite(value) && value >= .2 && value <= 3) next[key] = value;
          else if (key === 'volume' && Number.isFinite(value) && value >= 0 && value <= 100) next[key] = value;
          else if (key === 'lightingPreset' && ['calido', 'neutro', 'frio'].includes(value)) next[key] = value;
          else if (mode === 'local' && key === 'musicStyle' && ['ambiental', 'clasica', 'lofi', 'naturaleza', 'silencio'].includes(value)) next[key] = value;
          else if (mode === 'local' && key === 'focusMinutes' && Number.isInteger(value) && value >= 5 && value <= 120 && !state.sessionActive) next[key] = value;
          else if (mode === 'local' && key === 'sessionActive' && typeof value === 'boolean') { next[key] = value; next.sessionStartedAt = value ? (state.sessionActive ? state.sessionStartedAt : new Date().toISOString()) : null; }
          else throw new ApiError(400, 'Campo o valor no permitido');
        }
        if (mode === 'integrado' && link.linked && Object.keys(data).some(k => k !== 'volume') && !['finalizada', 'interrumpida'].includes(link.snapshot().estado)) throw new ApiError(409, 'Los ajustes visuales se fijaron al preparar la sesión; cerrar y crear otra para cambiarlos');
        if (mode === 'local') fs.writeFileSync(file, JSON.stringify(next));
        state = next; return json(res, 200, view(link.snapshot()), origin);
      }
      if (req.method === 'POST' && url.pathname === '/api/session/link') {
        if (mode !== 'integrado') throw new ApiError(409, 'Modo integrado desactivado');
        const data = await body(req);
        if (!/^[a-f\d]{24}$/.test(data.sesion_id || '') || !/^[\w-]{40,100}$/.test(data.codigo || '')) throw new ApiError(422, 'Código o sesión inválidos');
        const snapshot = await link.bind(data, bearer(req)); return json(res, 200, view(snapshot), origin);
      }
      if (req.method === 'POST' && url.pathname === '/api/session/release') return json(res, 200, view(await link.release(bearer(req))), origin);
      if (req.method === 'POST' && url.pathname === '/api/session/command') {
        if (mode !== 'integrado') throw new ApiError(409, 'Modo integrado desactivado');
        const data = await body(req); validateCommand(data); return json(res, 200, view(await link.command(data, bearer(req))), origin);
      }
      if (req.method === 'GET' && url.pathname === '/api/vr/state') {
        if (mode === 'integrado') roomAuth(req, roomKey);
        const snapshot = mode === 'integrado' ? await link.refresh() : {};
        seen = Date.now(); return json(res, 200, view(snapshot), origin);
      }
      if (req.method === 'POST' && url.pathname === '/api/vr/events') {
        if (mode !== 'integrado') throw new ApiError(409, 'No hay comandos integrados en modo local');
        roomAuth(req, roomKey); const data = await body(req); validateCommand(data);
        const snapshot = await link.confirm(data); seen = Date.now(); return json(res, 200, view(snapshot), origin);
      }
      if (req.method === 'GET' && !url.pathname.startsWith('/api/')) {
        const dist = path.join(root, 'web/dist');
        let target; try { target = path.resolve(dist, '.' + decodeURIComponent(url.pathname === '/' ? '/index.html' : url.pathname)); } catch { throw new ApiError(400, 'URL inválida'); }
        if (!target.startsWith(dist + path.sep)) throw new ApiError(403, 'Ruta inválida');
        if (!fs.existsSync(target) || !fs.statSync(target).isFile()) {
          if (path.extname(target)) throw new ApiError(404, 'Archivo no encontrado');
          target = path.join(dist, 'index.html');
        }
        if (!fs.existsSync(target)) throw new ApiError(404, 'Ejecutar npm run build o iniciar Vite');
        const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.wav': 'audio/wav', '.svg': 'image/svg+xml' };
        res.writeHead(200, { 'Content-Type': types[path.extname(target)] || 'application/octet-stream', 'X-Content-Type-Options': 'nosniff' });
        return fs.createReadStream(target).pipe(res);
      }
      throw new ApiError(404, 'Ruta no encontrada');
    } catch (error) {
      if (res.headersSent) { res.destroy(); return; }
      json(res, error.status || 500, { error: error.status ? error.message : 'Error interno del puente' }, allowed.has(origin) ? origin : undefined);
    }
  });
  server.requestTimeout = 20000;
  return server;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const env = path.join(root, '.env'); if (fs.existsSync(env)) process.loadEnvFile(env);
  const host = process.env.HOST || '127.0.0.1';
  if (!['127.0.0.1', 'localhost', '::1'].includes(host)) throw new Error('Este piloto solo permite loopback. No exponer el puente sin TLS y revisión de seguridad.');
  createBridge().listen(Number(process.env.PORT || 8788), host, () => console.log(`StudyRoom · ${process.env.MODE || 'local'} · http://${host}:${process.env.PORT || 8788}`));
}

// Prueba de transporte REAL contra las APIs Python con MongoDB SIMULADO.
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { randomBytes, randomUUID } from 'node:crypto';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import { createBridge } from '../bridge/server.mjs';
import { BackendClient } from '../bridge/backend-client.mjs';

const [python, source] = process.argv.slice(2);
if (!python || !source) throw new Error('Uso: node scripts/verify-python.mjs RUTA_PYTHON_DEL_BACKEND RUTA_FUENTES_BACKEND');
const fixture = fileURLToPath(new URL('../tests/python_http_fixture.py', import.meta.url));
const child = spawn(python, [fixture, '--source', source], { stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
let server;
try {
  const bases = await new Promise((resolve, reject) => {
    let output = '', errors = ''; const timer = setTimeout(() => reject(new Error('No inició la fixture Python')), 45000);
    child.on('error', e => { clearTimeout(timer); reject(e); });
    child.stderr.on('data', d => { errors += d; });
    child.on('exit', code => { clearTimeout(timer); reject(new Error(`Fixture Python terminó (${code}): ${errors.slice(-2000)}`)); });
    child.stdout.on('data', d => { output += d; if (output.includes('\n')) { clearTimeout(timer); try { resolve(JSON.parse(output.split('\n')[0])); } catch (e) { reject(e); } } });
  });
  const key = randomBytes(32).toString('hex');
  server = createBridge({ mode: 'integrado', roomKey: key, client: new BackendClient(bases) });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  const base = `http://127.0.0.1:${server.address().port}`;
  const call = async (method, path, body, headers = {}, status = 200) => {
    const response = await fetch(base + path, { method, headers: { ...headers, ...(body ? { 'Content-Type': 'application/json' } : {}) }, body: body ? JSON.stringify(body) : undefined });
    assert.equal(response.status, status, `${method} ${path}`); return response.json();
  };
  const credentials = { email: `http-${randomBytes(4).toString('hex')}@example.test`, password: randomBytes(20).toString('hex') };
  const register = { ...credentials, mayor_edad_confirmado: true, consentimiento_aceptado: true, consentimiento_version: 'consentimiento-v1' };
  await call('POST', '/backend/usuarios/auth/registro', { ...register, mayor_edad_confirmado: false }, {}, 422);
  await call('POST', '/backend/usuarios/auth/registro', register, {}, 201);
  const auth = await call('POST', '/backend/usuarios/auth/login', credentials);
  const web = { Authorization: `Bearer ${auth.access_token}` }, room = { 'X-Room-Key': key };
  await call('PUT', '/backend/usuarios/perfiles/me', { version_esperada: 1, artistas_preferidos: ['http-artist'], generos_preferidos: ['ambient'], tempo_preferido: 'lento' }, web);
  const session = await call('POST', '/backend/sesiones/sesiones', { solicitud_id: randomUUID(), actividad: { id: 'fixture-http', version: 'test', duracion_minutos: '25', brillo_multiplicador: '1.25', preset_iluminacion: 'neutro' }, modalidad: 'personalizada' }, web, 201);
  const sid = session._id;
  const request = { solicitud_id: randomUUID(), sesion_id: sid };
  const rec = await call('POST', '/backend/catalogo/recomendaciones', request, web, 201);
  assert.equal((await call('POST', '/backend/catalogo/recomendaciones', request, web, 201))._id, rec._id);
  const code = await call('POST', `/backend/sesiones/sesiones/${sid}/vinculacion`, {}, web);
  const binding = await call('POST', '/api/session/link', { sesion_id: sid, codigo: code.codigo }, web);
  assert.ok(!JSON.stringify(binding).includes('access_token'));
  const command = { id: randomUUID(), estado: 'activa' };
  await call('POST', '/api/session/command', command, web);
  assert.equal((await call('GET', `/backend/sesiones/sesiones/${sid}`, null, web)).estado, 'preparada');
  const state = await call('GET', '/api/vr/state', null, room);
  await call('POST', '/api/vr/events', state.pendiente, room);
  await call('POST', '/api/vr/events', state.pendiente, room);
  assert.equal((await call('GET', `/backend/sesiones/sesiones/${sid}`, null, web)).estado, 'activa');
  const song = rec.canciones[0];
  const audio = await fetch(base + `/backend/sesiones/audios/${song.audio_id}/contenido?sesion_id=${sid}`, { headers: { ...web, Range: 'bytes=0-9' } });
  assert.equal(audio.status, 206); assert.equal((await audio.arrayBuffer()).byteLength, 10);
  await call('POST', `/backend/sesiones/sesiones/${sid}/eventos`, { evento_id: randomUUID(), tipo: 'reproduccion_inicio', ocurrido_en: new Date().toISOString(), datos: { track_id: song.track_id, audio_id: song.audio_id, recomendacion_id: rec._id, reproduccion_id: randomUUID(), posicion_ms: 0, volumen: .2 } }, web);
  const feedback = { solicitud_id: randomUUID(), recomendacion_id: rec._id, track_id: song.track_id, preferencia: 'me_gusta', molestia: false };
  assert.equal((await call('POST', '/backend/catalogo/feedback', feedback, web, 201)).estado_ajuste, 'aplicado');
  const version = (await call('GET', '/backend/usuarios/perfiles/me', null, web)).version;
  await call('POST', '/backend/catalogo/feedback', feedback, web, 201);
  assert.equal((await call('GET', '/backend/usuarios/perfiles/me', null, web)).version, version);
  for (const estado of ['pausada', 'activa', 'finalizada']) { const cmd = { id: randomUUID(), estado }; await call('POST', '/api/session/command', cmd, web); await call('POST', '/api/vr/events', { ...cmd, sesion_id: sid }, room); }
  await call('POST', '/backend/usuarios/evaluaciones-tonos', {}, web, 503);
  await call('POST', `/backend/sesiones/sesiones/${sid}/encuesta`, { cuestionario_version: 'cuestionario-v1-borrador', respuestas: [] }, web, 503);
  await call('POST', '/api/session/release', {}, web);
  console.log('OK: React/proxy → APIs Python reales → puente/sala HTTP, audio Range, eventos, feedback idempotente y protocolos bloqueados. Base en memoria; MongoDB del estudio intacto.');
} finally {
  if (server) await new Promise(r => server.close(r));
  child.stdin.end('STOP\n');
  if (child.exitCode === null) await Promise.race([once(child, 'exit'), new Promise(r => setTimeout(r, 20000))]);
  if (child.exitCode === null) child.kill();
}

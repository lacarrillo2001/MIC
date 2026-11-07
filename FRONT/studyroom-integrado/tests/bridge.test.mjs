import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { createBridge } from '../bridge/server.mjs';
import { BackendClient } from '../bridge/backend-client.mjs';
import { SessionLink } from '../bridge/session-link.mjs';
import { fakeBackend } from './fake-backend.mjs';

function environment() { const fake = fakeBackend(); const client = new BackendClient({ usuarios: 'http://fake-users', catalogo: 'http://fake-catalogue', sesiones: 'http://fake-sessions' }, fake.fetch); return { fake, client }; }
async function runServer(t, options) { const server = createBridge(options); await new Promise(r => server.listen(0, '127.0.0.1', r)); t.after(() => new Promise(r => server.close(r))); return `http://127.0.0.1:${server.address().port}`; }
async function call(base, method, path, data, headers = {}) { const response = await fetch(base + path, { method, headers: { ...headers, ...(data ? { 'Content-Type': 'application/json' } : {}) }, body: data ? JSON.stringify(data) : undefined }); const json = await response.json(); return { status: response.status, json }; }
async function seed(client) { await client.json('sesiones', '/sesiones', { method: 'POST', token: 'web-demo', body: { actividad: { duracion_minutos: '25', brillo_multiplicador: '1.25', preset_iluminacion: 'neutro' } } }); await client.json('catalogo', '/recomendaciones', { method: 'POST', token: 'web-demo', body: {} }); }

test('YouTube web publica reproducción y feedback sin permitir rutas internas', async t => {
  const fake = fakeBackend({ youtubeConfigured: true });
  const client = new BackendClient({ usuarios: 'http://fake-users', catalogo: 'http://fake-catalogue', sesiones: 'http://fake-sessions' }, fake.fetch);
  const base = await runServer(t, { mode: 'integrado', roomKey: 'x'.repeat(64), client });
  const headers = { Authorization: 'Bearer web-demo' };
  assert.equal((await call(base, 'GET', '/backend/catalogo/catalogo/generos?q=ambiental', null, headers)).json[0].id, 'ambient');
  assert.equal((await call(base, 'POST', '/backend/catalogo/internal/generos/resolver', {generos:['ambiental']}, headers)).status, 404);
  const root = `/backend/catalogo/youtube/recomendaciones/${fake.rid}`;
  assert.equal((await call(base, 'POST', '/backend/catalogo/youtube/recomendaciones', { solicitud_id: 'test-youtube-request' }, headers)).status, 201);
  assert.equal((await call(base, 'POST', root + '/feedback', { track_id: 'fixture-video', respuesta: 'me_gusta', revision: 0 }, headers)).status, 409);
  assert.equal((await call(base, 'POST', root + '/reproduccion', { track_id: 'fixture-video' }, headers)).status, 200);
  assert.equal((await call(base, 'POST', root + '/feedback', { track_id: 'fixture-video', respuesta: 'me_gusta', revision: 0 }, headers)).json.revision, 1);
  assert.equal((await call(base, 'GET', '/backend/catalogo/youtube/feedback?pagina=1', null, headers)).json.length, 1);
  assert.equal((await call(base, 'POST', root + '/internal', {}, headers)).status, 404);
});

test('proxy publica la corrección de voz con autenticación y conserva sus datos', async t => {
  const calls = [];
  const client = new BackendClient({ catalogo: 'http://fake-catalogue' }, async (url, options) => {
    calls.push({ url, options });
    return Response.json({ tiene_voz: true, revision: 1 });
  });
  const base = await runServer(t, { mode: 'integrado', roomKey: 'x'.repeat(64), client });
  const route = '/backend/catalogo/youtube/recomendaciones/' + 'a'.repeat(24) + '/voz';
  const payload = {track_id:'song', tiene_voz:true, revision:0};
  assert.equal((await call(base, 'POST', route, payload, {Authorization:'Bearer web-demo'})).status, 200);
  assert.equal(calls[0].options.headers.Authorization, 'Bearer web-demo');
  assert.deepEqual(JSON.parse(calls[0].options.body), payload);
  assert.equal((await call(base, 'GET', route + '?track_id=song', null, {Authorization:'Bearer web-demo'})).status, 200);
  assert.ok(calls[1].url.endsWith('/voz?track_id=song'));
});

test('modo local conserva las rutas y no utiliza Python', async t => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'studyroom-test-')); t.after(() => fs.rmSync(dir, { recursive: true }));
  const base = await runServer(t, { mode: 'local', stateFile: path.join(dir, 'state.json') });
  assert.equal((await call(base, 'PATCH', '/api/state', { brightness: 2, sessionActive: true })).json.sessionActive, true);
  assert.equal((await call(base, 'GET', '/api/vr/state')).json.vrConnected, true);
  assert.equal((await call(base, 'GET', '/backend/usuarios/usuarios/me')).status, 409);
  assert.ok(fs.existsSync(path.join(dir, 'state.json')));
});
test('integrado exige autenticación de web, clave de sala y origen permitido', async t => {
  const { client } = environment(), base = await runServer(t, { mode: 'integrado', roomKey: 'x'.repeat(64), client });
  assert.equal((await call(base, 'GET', '/api/state')).status, 401);
  assert.equal((await call(base, 'GET', '/api/vr/state')).status, 403);
  assert.equal((await call(base, 'GET', '/api/config', null, { Origin: 'https://other.example' })).status, 403);
  assert.equal((await call(base, 'GET', '/api/config')).json.mode, 'integrado');
});
test('estado solo cambia con confirmación de Unreal; token de sala nunca se publica', async t => {
  const { client, fake } = environment(); await seed(client); const key = 'r'.repeat(64), base = await runServer(t, { mode: 'integrado', roomKey: key, client }), web = { Authorization: 'Bearer web-demo' }, room = { 'X-Room-Key': key };
  const bound = await call(base, 'POST', '/api/session/link', { sesion_id: fake.sid, codigo: 'c'.repeat(43) }, web);
  assert.equal(bound.status, 200); assert.ok(!JSON.stringify(bound.json).includes('room-demo'));
  const command = { id: 'command-0001', estado: 'activa' };
  assert.equal((await call(base, 'POST', '/api/session/command', command, web)).status, 200);
  assert.equal(fake.stats().session.estado, 'preparada');
  const poll = await call(base, 'GET', '/api/vr/state', null, room); assert.equal(poll.json.pendiente.id, command.id);
  assert.equal((await call(base, 'POST', '/api/vr/events', { ...command, sesion_id: fake.sid }, room)).status, 200);
  assert.equal((await call(base, 'POST', '/api/vr/events', { ...command, sesion_id: fake.sid }, room)).status, 200);
  assert.equal(fake.stats().transitions, 1);
  assert.equal((await call(base, 'PATCH', '/api/state', { sessionActive: false }, web)).status, 409);
  assert.equal((await call(base, 'PATCH', '/api/state', { brightness: 2 }, web)).status, 409);
  assert.equal((await call(base, 'POST', '/api/vr/events', { id: 'stop-00001', estado: 'interrumpida', sesion_id: fake.sid }, room)).status, 200);
  assert.equal(fake.stats().session.estado, 'interrumpida');
  assert.equal((await call(base, 'POST', '/api/session/release', {}, web)).status, 200);
});
test('se rechazan confirmaciones de otra sesión y comandos distintos simultáneos', async () => {
  const { client, fake } = environment(); await seed(client); const link = new SessionLink(client);
  await link.bind({ sesion_id: fake.sid, codigo: 'c'.repeat(43) }, 'web-demo');
  await link.command({ id: 'command-0001', estado: 'activa' }, 'web-demo');
  await assert.rejects(() => link.command({ id: 'command-0002', estado: 'activa' }, 'web-demo'), e => e.status === 409);
  await assert.rejects(() => link.confirm({ id: 'command-0001', estado: 'activa', sesion_id: 'other' }), e => e.status === 403);
  assert.equal(fake.stats().transitions, 0);
});
test('si falla Python no hay retorno silencioso al modo local', async t => {
  const client = new BackendClient({ usuarios: 'http://fake' }, async () => { throw new Error('offline'); });
  const base = await runServer(t, { mode: 'integrado', roomKey: 'x'.repeat(64), client });
  assert.equal((await call(base, 'GET', '/api/state', null, { Authorization: 'Bearer web-demo' })).status, 503);
  assert.equal((await call(base, 'GET', '/api/config')).json.mode, 'integrado');
});
test('proxy no publica internal, canje ni destinos arbitrarios; conserva bloqueos científicos', async t => {
  const { client, fake } = environment(), base = await runServer(t, { mode: 'integrado', roomKey: 'x'.repeat(64), client }), web = { Authorization: 'Bearer web-demo' };
  assert.equal((await call(base, 'GET', `/backend/usuarios/internal/usuarios/${fake.uid}/contexto`, null, web)).status, 404);
  assert.equal((await call(base, 'POST', `/backend/sesiones/sesiones/${fake.sid}/canje`, {}, web)).status, 404);
  assert.equal((await call(base, 'GET', '/backend/otro/usuarios/me', null, web)).status, 404);
  assert.equal((await call(base, 'POST', '/backend/usuarios/evaluaciones-tonos', {}, web)).status, 503);
  assert.equal(fake.stats().toneAttempts, 1);
  const youtube = await call(base, 'GET', '/backend/catalogo/youtube/configuracion', null, web);
  assert.equal(youtube.status, 200);
  assert.equal(youtube.json.configurado, false);
});
test('URL malformada y rutas de archivos faltantes no derriban el proceso', async t => {
  const base = await runServer(t, { mode: 'local' });
  assert.equal((await call(base, 'GET', '/%ZZ')).status, 400);
  assert.equal((await call(base, 'GET', '/not-a-file.wav')).status, 404);
  assert.equal((await call(base, 'GET', '/api/health')).status, 200);
});

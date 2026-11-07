// Vista de prueba aislada con datos sintéticos. Nunca conecta a MongoDB.
import { createBridge } from '../bridge/server.mjs';
import { BackendClient } from '../bridge/backend-client.mjs';
import { fakeBackend } from '../tests/fake-backend.mjs';
const fake = fakeBackend();
const key = 'preview-only-room-key-not-for-real-use-0123456789';
const client = new BackendClient({ usuarios: 'http://fake-users', catalogo: 'http://fake-catalogue', sesiones: 'http://fake-sessions' }, fake.fetch);
const server = createBridge({ mode: 'integrado', roomKey: key, client, origins: 'http://127.0.0.1:8790,http://localhost:8790' });
server.listen(8790, '127.0.0.1', () => console.log('Vista aislada: http://127.0.0.1:8790 · Cuenta sintética: demo@example.test / demo-password-123'));
// Simula únicamente el intercambio HTTP de Unreal, NO un visor ni compilación C++.
let working = false;
const timer = setInterval(async () => {
  if (working) return; working = true;
  try { const state = await fetch('http://127.0.0.1:8790/api/vr/state', { headers: { 'X-Room-Key': key } }).then(r => r.json()); if (state.pendiente) await fetch('http://127.0.0.1:8790/api/vr/events', { method: 'POST', headers: { 'X-Room-Key': key, 'Content-Type': 'application/json' }, body: JSON.stringify(state.pendiente) }); }
  catch {} finally { working = false; }
}, 1200);
process.on('SIGINT', () => { clearInterval(timer); server.close(() => process.exit()); });

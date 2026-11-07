// Solo prueba de frontend. No abre MongoDB ni llama a YouTube Data API.
// El video público sí se entrega mediante el reproductor oficial tras autorizarlo.
import { createBridge } from '../bridge/server.mjs';
import { BackendClient } from '../bridge/backend-client.mjs';
import { fakeBackend } from '../tests/fake-backend.mjs';
const fake = fakeBackend();
if (process.argv.includes('--audio-queue')) fake.enableAudioQueue();
const client = new BackendClient({ usuarios: 'http://fake-users', catalogo: 'http://fake-catalogue', sesiones: 'http://fake-sessions' }, fake.fetch);
const server = createBridge({ mode: 'integrado', roomKey: 'frontend-test-only-room-key-0123456789', client, origins: 'http://127.0.0.1:8792,http://localhost:8792' });
server.listen(8792, '127.0.0.1', () => console.log('PRUEBA AISLADA http://127.0.0.1:8792/?prueba=youtube-auto · Cuenta ficticia demo@example.test / demo-password-123 · Inicia con clave ausente simulada.'));
process.stdin.setEncoding('utf8');
process.stdin.on('data', data => {
  const command = data.trim();
  if (command === 'youtube-on') { fake.setYouTubeConfigured(true); console.log('SOLO FIXTURE: respuestas de búsqueda simuladas habilitadas, sin clave real.'); }
  if (command === 'audio-queue') { fake.enableAudioQueue(); console.log('SOLO FIXTURE: cola con fallo inicial y dos audios sintéticos de cuatro segundos.'); }
  if (command === 'stats') console.log(JSON.stringify({ resoluciones_simuladas: fake.stats().youtubeRequests, audio:fake.stats().audioEvents }));
  if (command === 'stop') server.close(() => process.exit());
});
process.on('SIGINT', () => server.close(() => process.exit()));

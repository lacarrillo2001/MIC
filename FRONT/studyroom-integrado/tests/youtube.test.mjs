import test from 'node:test';
import assert from 'node:assert/strict';
import { videoIdFromInput, playerErrorMessage } from '../web/src/api/youtube.js';
const id = 'M7lc1UVf-VE';
test('YouTube: admite ID y enlaces oficiales sin conservar parámetros ajenos', () => {
  for (const value of [id, `https://www.youtube.com/watch?v=${id}&t=30&list=ignored`, `https://youtu.be/${id}?si=ignored`, `https://m.youtube.com/watch?v=${id}`, `https://www.youtube.com/shorts/${id}`, `https://www.youtube.com/live/${id}`, `https://www.youtube-nocookie.com/embed/${id}`]) assert.equal(videoIdFromInput(value), id);
});
test('YouTube: rechaza otros dominios, protocolos, credenciales y entradas sin video', () => {
  for (const value of ['', 'javascript:alert(1)', `http://www.youtube.com/watch?v=${id}`, `https://youtube.com.evil.test/watch?v=${id}`, `https://user:secret@youtube.com/watch?v=${id}`, `https://youtu.be:444/${id}`, 'https://www.youtube.com/playlist?list=test', 'https://www.youtube.com/@channel', `https://youtube.com/watch?v=${id}&v=other`, '<iframe src="x"></iframe>']) assert.throws(() => videoIdFromInput(value));
});
test('YouTube: errores de inserción y origen son explícitos, sin evasión', () => {
  assert.match(playerErrorMessage(153), /origen/);
  assert.match(playerErrorMessage(101), /propietario/);
  assert.match(playerErrorMessage(100), /privado/);
});

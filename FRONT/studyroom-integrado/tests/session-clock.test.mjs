import test from 'node:test';
import assert from 'node:assert/strict';
import { secondsRemaining } from '../web/src/session-clock.mjs';

test('el reloj empieza al reproducir y vence sin reiniciarse al pausar o cambiar de canción', () => {
  const start = 1000000;
  assert.equal(secondsRemaining(null, 3, start), 180);
  assert.equal(secondsRemaining(start, 3, start), 180);
  assert.equal(secondsRemaining(start, 3, start + 90000), 90);
  assert.equal(secondsRemaining(start, 3, start + 180000), 0);
  assert.equal(secondsRemaining(start, 10, start + 599001), 1);
  assert.equal(secondsRemaining(start, 10, start + 700000), 0);
});

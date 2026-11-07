import React, { useEffect, useRef, useState } from 'react';
import { songAudio, event } from '../api/sesiones.js';
import { feedback } from '../api/recomendaciones.js';
import { newId } from '../api/client.js';

function Track({ song, rec, session, enqueue }) {
  const audio = useRef(null), objectUrl = useRef(''), playback = useRef(newId()), alive = useRef(true), volumeTimer = useRef(null), played = useRef(false);
  const current = useRef(session); current.current = session;
  const [src, setSrc] = useState(''), [busy, setBusy] = useState(false), [message, setMessage] = useState(''), [preference, setPreference] = useState(''), [discomfort, setDiscomfort] = useState('');
  const operation = useRef(null);
  function report(tipo) {
    const node = audio.current;
    if (!node || !['activa', 'pausada'].includes(current.current.estado)) return;
    enqueue({ evento_id: newId(), tipo, ocurrido_en: new Date().toISOString(), datos: { track_id: song.track_id, audio_id: song.audio_id, recomendacion_id: rec._id, reproduccion_id: playback.current, posicion_ms: Math.round(node.currentTime * 1000), volumen: node.volume, ...(tipo === 'error' ? { error: 'Error del reproductor del navegador' } : {}) } });
  }
  useEffect(() => { alive.current = true; return () => { alive.current = false; clearTimeout(volumeTimer.current); audio.current?.pause(); if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); }; }, []);
  useEffect(() => { if (session.estado !== 'activa') audio.current?.pause(); }, [session.estado]);
  async function load() { setBusy(true); setMessage(''); try { const blob = await songAudio(song.audio_id, session._id); if (!alive.current) return; if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); objectUrl.current = URL.createObjectURL(blob); setSrc(objectUrl.current); } catch (e) { if (alive.current) setMessage(e.message); } finally { if (alive.current) setBusy(false); } }
  async function save() {
    setBusy(true); const values = { recomendacion_id: rec._id, track_id: song.track_id, preferencia: preference || null, molestia: discomfort === '' ? null : discomfort === 'true' };
    if (!operation.current || operation.current.key !== JSON.stringify(values)) operation.current = { key: JSON.stringify(values), body: { solicitud_id: newId(), ...values } };
    try { const result = await feedback(operation.current.body); setMessage(result.estado_ajuste === 'pendiente' ? 'Valoración guardada; ajuste pendiente. Reenvía la misma valoración para reintentar.' : 'Valoración guardada para futuras sesiones.'); } catch (e) { setMessage(e.message); } finally { setBusy(false); }
  }
  return <div className="track-detail"><h3>{song.name || song.track_id}</h3><p>{song.artists?.join(', ')}</p><p>Compatibilidad: {song.puntaje_compatibilidad} · No es una puntuación de atención.</p><details><summary>Por qué aparece</summary><ul>{song.motivos.map((m, i) => <li key={i}>{m}</li>)}</ul></details><button disabled={busy || !['activa', 'pausada'].includes(session.estado)} onClick={load}>Cargar audio autorizado</button>
    <audio ref={audio} src={src || undefined} controls preload="none" onPlay={() => { if (session.estado !== 'activa') { audio.current.pause(); setMessage('Inicia o reanuda la actividad desde Unreal antes de reproducir.'); return; } played.current = true; report('reproduccion_inicio'); }} onPause={() => { if (played.current && !audio.current?.ended) report('reproduccion_pausa'); }} onEnded={() => report('reproduccion_fin')} onError={() => { if (src) { report('error'); setMessage('No se pudo reproducir el archivo.'); } }} onVolumeChange={() => { clearTimeout(volumeTimer.current); if (played.current) volumeTimer.current = setTimeout(() => report('volumen'), 500); }} />
    <button disabled={!['activa', 'pausada'].includes(session.estado)} onClick={() => { report('omision'); audio.current?.pause(); setMessage('Omisión registrada; no implica rechazo automático.'); }}>Registrar omisión</button>
    <div className="feedback-grid"><label>Preferencia<select value={preference} onChange={e => setPreference(e.target.value)}><option value="">Sin declarar</option><option value="me_gusta">Me gusta</option><option value="no_me_gusta">No me gusta</option><option value="neutral">Neutral</option></select></label><label>Molestia auditiva<select value={discomfort} onChange={e => setDiscomfort(e.target.value)}><option value="">Sin declarar</option><option value="false">No</option><option value="true">Sí</option></select></label></div><button disabled={busy || !session.inicio || (!preference && !discomfort)} onClick={save}>Guardar valoración</button><p role="status">{message}</p>
  </div>;
}
export default function Reproductor({ rec, session, onPending }) {
  const [index, setIndex] = useState(0), [count, setCount] = useState(0), [error, setError] = useState(''); const queue = useRef([]), flushing = useRef(false);
  async function flush() { if (flushing.current) return; flushing.current = true; try { while (queue.current.length) { await event(session._id, queue.current[0]); queue.current.shift(); setCount(queue.current.length); onPending(queue.current.length); } setError(''); } catch (e) { setError('Eventos pendientes: ' + e.message); } finally { flushing.current = false; } }
  function enqueue(data) { if (queue.current.length >= 100) { setError('Límite local alcanzado. Detén la reproducción y recupera la conexión.'); return; } queue.current.push(data); setCount(queue.current.length); onPending(queue.current.length); void flush(); }
  if (!rec || !session) return <section className="panel"><h2>Tu música</h2><p>Prepara una sesión para recibir canciones del catálogo con archivos autorizados.</p></section>;
  return <section className="panel" id="musica"><div className="eyebrow">RECOMENDACIÓN PERSONALIZADA</div><h2>Tu música</h2><label>Canción<select value={index} onChange={e => { if (document.querySelector('#musica audio') && !document.querySelector('#musica audio').paused) { setError('Pausa la canción antes de seleccionar otra.'); return; } setIndex(Number(e.target.value)); }}>{rec.canciones.map((s, i) => <option key={s.track_id} value={i}>{i + 1}. {s.name || s.track_id}</option>)}</select></label><Track key={rec.canciones[index].audio_id} song={rec.canciones[index]} rec={rec} session={session} enqueue={enqueue} />{count > 0 && <button onClick={flush}>Reintentar {count} eventos pendientes</button>}{error && <p role="alert" className="form-error">{error}</p>}<p>Se reproduce en la salida de audio del navegador, no dentro de Unreal.</p></section>;
}

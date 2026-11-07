import React, { useEffect, useRef, useState } from 'react';
import { toneConfig, startTones, finishTones } from '../api/usuarios.js';
import { toneAudio } from '../api/sesiones.js';
export default function EvaluacionTonos({ locked }) {
  const [cfg, setCfg] = useState(null), [evaluation, setEvaluation] = useState(null), [index, setIndex] = useState(0), [answers, setAnswers] = useState([]), [agrado, setAgrado] = useState(''), [molestia, setMolestia] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false), [source, setSource] = useState('');
  const audio = useRef(null), objectUrl = useRef('');
  useEffect(() => { let current = true; toneConfig().then(c => current && setCfg(c)).catch(e => current && setMessage(e.message)); return () => { current = false; audio.current?.pause(); if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); }; }, []);
  const tone = evaluation?.configuracion_utilizada.tonos[index];
  async function start() { setBusy(true); try { setEvaluation(await startTones()); setAnswers([]); setIndex(0); setMessage('Detén u omite el sonido si sientes incomodidad.'); } catch (e) { setMessage(e.message); } finally { setBusy(false); } }
  async function play() {
    setBusy(true); try { audio.current?.pause(); if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); const file = await toneAudio(evaluation.audios_utilizados[tone.tono_id].audio_id, evaluation._id); objectUrl.current = URL.createObjectURL(file); setSource(objectUrl.current); }
    catch (e) { setMessage(e.message); } finally { setBusy(false); }
  }
  async function answer(omitido = false, interrupted = false) {
    audio.current?.pause(); setBusy(true);
    const next = tone && !interrupted ? [...answers, { tono_id: tone.tono_id, audio_id: evaluation.audios_utilizados[tone.tono_id].audio_id, frecuencia_hz: tone.frecuencia_hz, orden: index + 1, agrado: omitido ? null : Number(agrado), molestia: omitido ? null : Number(molestia), omitido }] : answers;
    try {
      if (interrupted || index === evaluation.configuracion_utilizada.tonos.length - 1) {
        await finishTones(evaluation._id, { estado: interrupted ? 'interrumpida' : 'completada', respuestas: next });
        setEvaluation(null); setMessage(interrupted ? 'Evaluación interrumpida. No se convierte en una evaluación completada.' : 'Evaluación completada.');
      } else { setAnswers(next); setIndex(i => i + 1); }
      setSource(''); setAgrado(''); setMolestia('');
    } catch (e) { setMessage(e.message); } finally { setBusy(false); }
  }
  const values = cfg ? Array.from({ length: cfg.escala.max - cfg.escala.min + 1 }, (_, i) => cfg.escala.min + i) : [];
  return <section className="panel"><div className="eyebrow">PERCEPCIÓN AUDITIVA</div><h2>Evaluación de tonos</h2><p>No es un diagnóstico auditivo ni una medición de la frecuencia de las canciones.</p>
    {!cfg?.aprobado ? <div className="info-note">Protocolo pendiente de aprobación. La evaluación permanece deshabilitada.</div> : !evaluation ? <button disabled={locked || busy} onClick={start}>Iniciar evaluación aprobada</button> : <><h3>Tono {index + 1} · {tone.frecuencia_hz} Hz</h3><button disabled={busy} onClick={play}>Cargar sonido</button><audio ref={audio} controls src={source || undefined} preload="none" />
      {['agrado', 'molestia'].map(key => <label key={key}>{key === 'agrado' ? 'Agrado' : 'Molestia'} ({cfg.escala.min}–{cfg.escala.max})<select value={key === 'agrado' ? agrado : molestia} onChange={e => (key === 'agrado' ? setAgrado : setMolestia)(e.target.value)}><option value="">Seleccionar</option>{values.map(v => <option key={v} value={v}>{v} · {cfg.escala[key]?.[String(v)] || ''}</option>)}</select></label>)}
      <div className="button-row"><button disabled={busy || !agrado || !molestia} onClick={() => answer()}>Guardar respuesta</button><button disabled={busy} onClick={() => answer(true)}>Omitir tono</button><button disabled={busy} onClick={() => answer(false, true)}>Interrumpir evaluación</button></div></>}
    <p role="status">{message}</p>
  </section>;
}

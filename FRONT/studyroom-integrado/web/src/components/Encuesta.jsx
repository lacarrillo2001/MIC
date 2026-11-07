import React, { useEffect, useState } from 'react';
import { questionnaire, survey } from '../api/sesiones.js';
export default function Encuesta({ session }) {
  const [cfg, setCfg] = useState(null), [values, setValues] = useState({}), [message, setMessage] = useState(''), [busy, setBusy] = useState(false), [saved, setSaved] = useState(false);
  useEffect(() => { let current = true; questionnaire().then(c => current && setCfg(c)).catch(e => current && setMessage(e.message)); return () => { current = false; }; }, []);
  async function submit(e) { e.preventDefault(); setBusy(true); try { await survey(session._id, { cuestionario_version: cfg.version, respuestas: cfg.preguntas.map(p => ({ pregunta_id: p.pregunta_id, valor: Number(values[p.pregunta_id]) })) }); setSaved(true); setMessage('Encuesta guardada.'); } catch (e) { setMessage(e.message); } finally { setBusy(false); } }
  const closed = ['finalizada', 'interrumpida'].includes(session?.estado) && session?.inicio;
  return <section className="panel"><div className="eyebrow">DESPUÉS DE LA ACTIVIDAD</div><h2>Tu experiencia</h2><p>Recogemos atención percibida, no una medida objetiva del desempeño.</p>
    {!cfg?.aprobado ? <div className="info-note">Cuestionario pendiente de aprobación. No se enviarán respuestas de un instrumento provisional.</div> : !closed ? <p>Disponible al cerrar una actividad que haya comenzado.</p> : <form onSubmit={submit}><fieldset disabled={busy || saved}>{cfg.preguntas.map(p => <label key={p.pregunta_id}>{p.texto}<select required value={values[p.pregunta_id] || ''} onChange={e => setValues(v => ({ ...v, [p.pregunta_id]: e.target.value }))}><option value="">Seleccionar ({p.min}–{p.max})</option>{Array.from({ length: p.max - p.min + 1 }, (_, i) => p.min + i).map(v => <option key={v} value={v}>{v}</option>)}</select></label>)}<button>Guardar encuesta</button></fieldset></form>}<p role="status">{message}</p>
  </section>;
}

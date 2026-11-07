import React, { useEffect, useState } from 'react';
import { request } from '../api/client.js';

// Sincroniza la respuesta visible en el reproductor y en su historial de esta pestaña.
const changes = new EventTarget();

export default function YouTubeFeedback({ recommendationId, song, result, played }) {
  const [answer, setAnswer] = useState(result.respuesta_actual || 'neutral');
  const [revision, setRevision] = useState(result.revision_feedback || 0);
  const [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  useEffect(() => {
    const changed = event => {
      if (event.detail.track_id !== song.track_id) return;
      setAnswer(event.detail.respuesta); setRevision(event.detail.revision);
    };
    changes.addEventListener('saved', changed);
    return () => changes.removeEventListener('saved', changed);
  }, [song.track_id]);
  async function save(respuesta) {
    setBusy(true); setMessage('');
    try {
      const saved = await request(`/backend/catalogo/youtube/recomendaciones/${recommendationId}/feedback`, {
        method: 'POST', body: { track_id: song.track_id, respuesta, revision },
      });
      setAnswer(saved.respuesta); setRevision(saved.revision);
      changes.dispatchEvent(new CustomEvent('saved', { detail: saved }));
      setMessage('Respuesta guardada. Se aplicará a las próximas listas; puedes corregirla.');
    } catch (e) { setMessage(e.message); } finally { setBusy(false); }
  }
  return <section aria-label="Tu opinión sobre la canción">
    <h3>¿Qué te pareció esta canción?</h3>
    <p>{played ? 'Tu respuesta ajusta las próximas recomendaciones.' : 'Reproduce la canción para poder valorarla.'}</p>
    <div className="youtube-actions">
      {[['me_gusta', 'Me gusta'], ['no_me_gusta', 'No me gusta'], ['molestia', 'Me causa molestia'], ['neutral', 'Retirar respuesta']].map(([value, label]) =>
        <button key={value} aria-pressed={answer === value} disabled={!played || busy || answer === value} onClick={() => save(value)}>{label}</button>)}
    </div>
    <p>La molestia se registra para esta canción; no se atribuye a una frecuencia sonora.</p>
    <p role="status">{message}</p>
  </section>;
}

export function FeedbackHistory() {
  const [items, setItems] = useState([]), [page, setPage] = useState(1), [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function load(number) {
    setBusy(true); setError('');
    try { setItems(await request(`/backend/catalogo/youtube/feedback?pagina=${number}`)); setPage(number); }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  return <details className="youtube-privacy"><summary>Revisar o retirar mis valoraciones anteriores</summary>
    <button disabled={busy} onClick={() => load(1)}>Cargar valoraciones</button>
    <p>Puedes corregir un rechazo o retirar una valoración aunque la canción ya no aparezca en tus listas.</p>
    {items.map(item => <article key={`${item._id}:${item.revision}`}><h3>{item.name || item.track_id}</h3><p>{item.artists?.join(', ')}</p>
      <YouTubeFeedback recommendationId={item.recomendacion_id} song={item} result={{ respuesta_actual: item.respuesta, revision_feedback: item.revision }} played />
    </article>)}
    <div className="youtube-actions"><button disabled={busy || page === 1} onClick={() => load(page - 1)}>Anteriores</button><button disabled={busy || items.length < 20} onClick={() => load(page + 1)}>Más valoraciones</button></div>
    <p role="status">{error}</p>
  </details>;
}

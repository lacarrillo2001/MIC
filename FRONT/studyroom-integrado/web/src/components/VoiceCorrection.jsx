import React, { useEffect, useState } from 'react';
import { request } from '../api/client.js';

export default function VoiceCorrection({ recommendationId, song, played }) {
  const [value, setValue] = useState(null), [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  const url = `/backend/catalogo/youtube/recomendaciones/${recommendationId}/voz`;
  useEffect(() => {
    let alive = true;
    request(`${url}?track_id=${encodeURIComponent(song.track_id)}`)
      .then(data => { if (alive) setValue(data); })
      .catch(e => { if (alive) setMessage(e.message); });
    return () => { alive = false; };
  }, [url, song.track_id]);
  async function save(tiene_voz) {
    setBusy(true); setMessage('');
    try {
      const data = await request(url, { method: 'POST', body: { track_id: song.track_id, tiene_voz, revision: value.revision } });
      setValue(data);
      setMessage(tiene_voz ? 'Corrección guardada. Esta canción se evitará en tus próximas listas instrumentales. No cambia tu valoración musical.' : 'Corrección retirada. La canción vuelve a evaluarse con los datos del catálogo; no queda confirmada como instrumental.');
    } catch (e) { setMessage(e.message); }
    finally { setBusy(false); }
  }
  return <section aria-label="Corregir presencia de voz">
    <p>{value?.tiene_voz ? 'Voz reportada por ti; letra sin verificar.' : song.clasificacion_voz || 'Presencia de voz sin verificar.'}</p>
    <button disabled={!played || !value || busy || value.tiene_voz} onClick={() => save(true)}>Esta canción tiene voz</button>
    {value?.tiene_voz && <button disabled={!played || busy} onClick={() => save(false)}>Retirar corrección de voz</button>}
    <p>Informa si escuchas canto, habla o vocalizaciones. Es independiente de Me gusta y no confirma que tenga letra.</p>
    <p role="status">{message}</p>
  </section>;
}

export function VoiceHistory() {
  const [items, setItems] = useState([]), [page, setPage] = useState(1), [busy, setBusy] = useState(false), [message, setMessage] = useState('');
  async function load(number) {
    setBusy(true); setMessage('');
    try { const rows = await request(`/backend/catalogo/youtube/voz?pagina=${number}`); setItems(rows); setPage(number); if (!rows.length) setMessage('No hay correcciones de voz en esta página.'); }
    catch (e) { setMessage(e.message); }
    finally { setBusy(false); }
  }
  return <details className="youtube-privacy"><summary>Revisar mis correcciones de voz</summary>
    <button disabled={busy} onClick={() => load(1)}>Cargar correcciones de voz</button>
    {items.map(item => <article key={`${item._id}:${item.revision}`}><h3>{item.name}</h3><p>{item.artists?.join(', ')}</p><VoiceCorrection recommendationId={item.recomendacion_id} song={item} played /></article>)}
    <div className="youtube-actions"><button disabled={busy || page === 1} onClick={() => load(page - 1)}>Correcciones anteriores</button><button disabled={busy || items.length < 20} onClick={() => load(page + 1)}>Más correcciones</button></div>
    <p role="status">{message}</p>
  </details>;
}

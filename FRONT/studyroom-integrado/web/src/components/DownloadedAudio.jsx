import React, { useEffect, useRef, useState } from 'react';
import { request } from '../api/client.js';

export default function DownloadedAudio({ rec, song, autoplay, onPlaying, onEnded, onUnavailable, volume = .4, onVolumeChange }) {
  const [src, setSrc] = useState(''), [status, setStatus] = useState('Preparando audio…');
  const [error, setError] = useState(''), [attempt, setAttempt] = useState(0);
  const node = useRef(null), callbacks = useRef({}); callbacks.current = {onPlaying,onEnded,onUnavailable,volume,onVolumeChange};
  const failure = useRef(false);
  function unavailable(message) { if (!failure.current) { failure.current=true; callbacks.current.onUnavailable?.(message); } }
  useEffect(() => {
    if (!src || !node.current) return;
    node.current.volume = callbacks.current.volume;
    if (autoplay) node.current.play().catch(() => setStatus('Pulsa Reproducir para continuar la lista.'));
  }, [src, autoplay]);
  useEffect(() => {
    let alive = true, timer, objectUrl, running = false; const deadline = Date.now() + 360000;
    const controller = new AbortController(); failure.current=false; setSrc(''); setError(''); setStatus('Solicitando audio…');
    async function load() {
      if (!alive) return;
      if (Date.now() > deadline) { setError('La preparación ha tardado demasiado. Puedes reintentar o elegir otra canción.'); return; }
      try {
        const result = await request('/backend/sesiones/descargas', {method:'POST', signal:controller.signal,
          body:{recomendacion_id:rec._id,track_id:song.track_id}});
        async function poll() {
          if (!alive || running) return; running = true;
          if (Date.now() > deadline) { clearInterval(timer); setError('La preparación ha tardado demasiado. Reintenta para consultar o recuperar la descarga.'); running=false; return; }
          try {
            const item = await request(`/backend/sesiones/descargas/${result.audio_id}?recomendacion_id=${rec._id}`, {signal:controller.signal});
            if (!alive) return;
            if (item.estado === 'error') { clearInterval(timer); const message=item.error || 'Descarga fallida'; setError(message); setStatus('Audio no disponible.'); unavailable(message); return; }
            if (item.estado === 'disponible') {
              clearInterval(timer); setStatus('Cargando archivo de audio…');
              const blob = await request(`/backend/sesiones/descargas/${result.audio_id}/contenido?recomendacion_id=${rec._id}`, {blob:true, signal:controller.signal});
              if (!alive) return;
              objectUrl = URL.createObjectURL(blob); setSrc(objectUrl); setStatus('Audio listo. Pulsa Reproducir.');
            } else setStatus('Descargando y convirtiendo a MP3…');
          } catch (e) { if (alive) { clearInterval(timer); setError(e.message); } } finally { running = false; }
        }
        timer = setInterval(poll, 2000); await poll();
      } catch (e) { if (alive) { if (e.status===429) { setStatus('Esperando a que termine la descarga anterior…'); timer=setTimeout(load,2000); } else {setError(e.message); if ([404,422].includes(e.status)) unavailable(e.message);} } }
    }
    void load();
    return () => { alive = false; clearInterval(timer); clearTimeout(timer); controller.abort(); node.current?.pause(); if(objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [rec._id, song.track_id, attempt]);
  return <section aria-label="Reproductor de audio descargado"><p role="status">{status}</p>
    {src && <audio ref={node} controls src={src} onVolumeChange={() => callbacks.current.onVolumeChange?.(node.current.volume)}
      onPlay={() => {setStatus('Reproduciendo audio.'); callbacks.current.onPlaying();}}
      onPause={() => setStatus('Audio pausado.')} onEnded={() => {setStatus('Canción finalizada.');callbacks.current.onEnded();}}
      onError={() => { const message='El navegador no pudo reproducir el archivo.';setError(message);unavailable(message); }} />}
    {error && <><p role="alert">{error}</p><button onClick={() => setAttempt(a=>a+1)}>Reintentar descarga</button><a href="/?prueba=youtube-auto">Usar reproductor oficial de YouTube</a></>}
    <p>El audio queda guardado para próximas reproducciones.</p>
  </section>;
}

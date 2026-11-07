import React, { useEffect, useRef, useState } from 'react';
import { loadYouTubeApi, playerErrorMessage, videoIdFromInput } from '../api/youtube.js';
import './youtube-demo.css';

export default function YouTubeDemo() {
  const [input, setInput] = useState(''), [video, setVideo] = useState(null), [consent, setConsent] = useState(false), [error, setError] = useState(''), [status, setStatus] = useState('Sin video cargado.');
  const host = useRef(null), player = useRef(null), visible = useRef(true), ready = useRef(false);
  useEffect(() => {
    if (!video) return;
    let cancelled = false;
    ready.current = false;
    setStatus('Conectando con el reproductor oficial…');
    let observer, readyTimeout;
    const pause = () => { if (ready.current) player.current?.pauseVideo?.(); };
    const visibility = () => { if (document.hidden) pause(); };
    document.addEventListener('visibilitychange', visibility);
    loadYouTubeApi().then(YT => {
      if (cancelled || !host.current) return;
      const iframe = document.createElement('iframe');
      iframe.title = 'Reproductor oficial de YouTube';
      iframe.width = '640'; iframe.height = '360';
      iframe.allow = 'encrypted-media; picture-in-picture; fullscreen';
      iframe.allowFullscreen = true;
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      const embed = new URL(`https://www.youtube-nocookie.com/embed/${video.id}`);
      embed.search = new URLSearchParams({ enablejsapi: '1', origin: window.location.origin, autoplay: '0', playsinline: '1', controls: '1' }).toString();
      iframe.src = embed.toString();
      host.current.replaceChildren(iframe);
      player.current = new YT.Player(iframe, { events: {
        onReady: () => { clearTimeout(readyTimeout); if (!cancelled) { ready.current = true; setStatus('Listo. Pulsa Reproducir en el video.'); } },
        onStateChange: e => {
          if (cancelled) return;
          if (e.data === 1 && (document.hidden || !visible.current)) { pause(); return; }
          const states = { '-1': 'Video cargado; pulsa Reproducir.', 0: 'Video finalizado.', 1: 'Reproduciendo desde YouTube.', 2: 'Reproducción pausada.', 3: 'Cargando contenido…', 5: 'Video preparado.' };
          if (states[e.data]) setStatus(states[e.data]);
        },
        onError: e => { clearTimeout(readyTimeout); if (!cancelled) { setError(playerErrorMessage(e.data)); setStatus('No se pudo reproducir este video.'); } },
        onAutoplayBlocked: () => { if (!cancelled) setStatus('El navegador solicita interacción: pulsa Reproducir dentro del video.'); },
      } });
      readyTimeout = setTimeout(() => { if (!cancelled && !ready.current) { setError('YouTube no confirmó la carga. Revisa tu conexión o abre esta misma página en Chrome o Edge. No se omitirán restricciones del reproductor.'); setStatus('Carga del video sin confirmar.'); } }, 25000);
      observer = new IntersectionObserver(entries => { visible.current = entries[0].intersectionRatio >= .5; if (!visible.current) pause(); }, { threshold: [.5] });
      observer.observe(host.current);
    }).catch(e => { if (!cancelled) { setError(e.message); setStatus('Reproductor no disponible.'); } });
    return () => { cancelled = true; clearTimeout(readyTimeout); document.removeEventListener('visibilitychange', visibility); observer?.disconnect(); player.current?.destroy?.(); player.current = null; ready.current = false; host.current?.replaceChildren(); };
  }, [video]);

  function load(e) { e.preventDefault(); try { if (!consent) throw new Error('Permite la conexión a YouTube para cargar el video.'); const id = videoIdFromInput(input); setError(''); setVideo({ id }); } catch (e) { setError(e.message); } }
  return <main className="youtube-page"><header className="youtube-header"><a href="/">StudySpace VR</a><span>Prueba web · YouTube</span></header><section className="youtube-card"><div className="eyebrow">REPRODUCCIÓN DIRECTA · SIN DESCARGAS</div><h1>Probemos tu música<br /><em>desde YouTube.</em></h1><p>Pega el enlace de un video. Se mostrará el reproductor oficial con sus controles; esta prueba no necesita iniciar sesión en nuestro sistema.</p>
    <form onSubmit={load}><label htmlFor="youtube-url">Enlace o ID del video</label><div className="youtube-input-row"><input id="youtube-url" value={input} onChange={e => setInput(e.target.value)} placeholder="https://www.youtube.com/watch?v=…" maxLength={1000} required autoComplete="off" /><button type="submit" disabled={!consent}>Cargar video</button></div>
      <label className="youtube-consent"><input type="checkbox" checked={consent} onChange={e => { setConsent(e.target.checked); if (!e.target.checked) { setVideo(null); setStatus('Conexión detenida.'); } }} />Permitir la conexión a YouTube. Google recibirá las solicitudes del reproductor y podrá tratar datos según su política de privacidad.</label></form>
    <details className="youtube-privacy"><summary>Privacidad y alcance de esta prueba</summary><p>Esta página utiliza los servicios API de YouTube. No solicita credenciales de Google, no busca videos automáticamente ni envía tu perfil musical, tokens o datos de la tesis a YouTube. El ID del video se mantiene solo en memoria de esta pestaña; no se almacena en MongoDB. Google recibe la conexión y los datos que genere su reproductor. Al usarlo, se aplican los <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer">Términos de YouTube</a> y la <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">Política de privacidad de Google</a>.</p></details>
    {error && <div className="youtube-error" role="alert">{error}</div>}<div className="youtube-player" ref={host} aria-label="Área del reproductor de YouTube" />{!video && <div className="youtube-empty">El video aparecerá aquí después de cargarlo.<br /><small>No se contacta con YouTube hasta que lo solicites.</small></div>}<p role="status" className="youtube-status">{status}</p>
    {video && <div className="youtube-actions"><button onClick={() => { setVideo(null); setStatus('Video retirado; reproductor detenido.'); }}>Detener y retirar video</button><a href={`https://www.youtube.com/watch?v=${video.id}`} target="_blank" rel="noreferrer">Abrir en YouTube ↗</a></div>}
    <aside className="youtube-note"><strong>Solo prueba de reproducción web.</strong> No está asociada con las recomendaciones de <code>songsV2</code> ni registra eventos del estudio. Mantén el reproductor visible: se pausa al ocultar la pestaña o desplazarlo fuera de vista. No utilizarlo como audio de fondo durante Unreal. Anuncios, restricciones o versiones diferentes pueden afectar la prueba.</aside>
  </section></main>;
}

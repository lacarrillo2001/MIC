import React, { useEffect, useRef, useState } from 'react';
import { loadYouTubeApi, playerErrorMessage } from '../api/youtube.js';

export default function OfficialYouTubePlayer({ videoId, autoplay, onEnded, onUnavailable, onPlaying }) {
  const host = useRef(null), player = useRef(null), callbacks = useRef({ onEnded, onUnavailable, onPlaying });
  callbacks.current = { onEnded, onUnavailable, onPlaying };
  const [status, setStatus] = useState('Preparando reproductor oficial…');
  useEffect(() => {
    let cancelled = false, ready = false, visible = false, observer, timer, failureReported = false;
    const pause = () => { if (ready) player.current?.pauseVideo?.(); };
    const changed = () => { if (document.hidden) pause(); };
    document.addEventListener('visibilitychange', changed);
    loadYouTubeApi().then(YT => {
      if (cancelled || !host.current) return;
      const iframe = document.createElement('iframe');
      iframe.title = 'Reproductor oficial de YouTube'; iframe.width = '640'; iframe.height = '360';
      iframe.allow = 'autoplay; encrypted-media; picture-in-picture; fullscreen'; iframe.allowFullscreen = true;
      iframe.referrerPolicy = 'strict-origin-when-cross-origin';
      const url = new URL(`https://www.youtube-nocookie.com/embed/${videoId}`);
      url.search = new URLSearchParams({ enablejsapi: '1', origin: location.origin, playsinline: '1', controls: '1', autoplay: '0' });
      iframe.src = url.toString(); host.current.replaceChildren(iframe);
      player.current = new YT.Player(iframe, { events: {
        onReady: () => { if (cancelled) return; ready = true; clearTimeout(timer); setStatus('Pulsa Reproducir en el video.'); if (autoplay && !document.hidden && visible) player.current.playVideo(); },
        onStateChange: e => { if (cancelled) return; if (e.data === 1 && (document.hidden || !visible)) { pause(); return; } if (e.data === 1) { setStatus('Reproduciendo desde YouTube.'); callbacks.current.onPlaying?.(); } if (e.data === 2) setStatus('Pausado.'); if (e.data === 0) { setStatus('Finalizado; buscando la siguiente canción…'); callbacks.current.onEnded(); } },
        onError: e => { if (cancelled) return; clearTimeout(timer); setStatus(playerErrorMessage(e.data)); if ([100, 101, 150].includes(e.data) && !failureReported) { failureReported = true; callbacks.current.onUnavailable(playerErrorMessage(e.data)); } },
        onAutoplayBlocked: () => { if (!cancelled) setStatus('El navegador bloqueó el inicio automático. Pulsa Reproducir dentro del video.'); },
      } });
      timer = setTimeout(() => { if (!cancelled && !ready) setStatus('YouTube no confirmó la carga. Revisa la conexión o prueba Chrome/Edge.'); }, 25000);
      observer = new IntersectionObserver(entries => { visible = entries[0].intersectionRatio >= .5; if (!visible) pause(); }, { threshold: [.5] });
      observer.observe(host.current);
    }).catch(e => { if (!cancelled) setStatus(e.message); });
    return () => { cancelled = true; clearTimeout(timer); observer?.disconnect(); document.removeEventListener('visibilitychange', changed); player.current?.destroy?.(); player.current = null; host.current?.replaceChildren(); };
  }, [videoId, autoplay]);
  return <><div className="youtube-player" ref={host} /><p role="status" className="youtube-status">{status}</p></>;
}

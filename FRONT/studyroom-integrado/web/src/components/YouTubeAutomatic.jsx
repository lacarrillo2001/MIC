import React, { useEffect, useRef, useState } from 'react';
import Acceso from './Acceso.jsx';
import OfficialYouTubePlayer from './OfficialYouTubePlayer.jsx';
import Preferencias from './Preferencias.jsx';
import YouTubeFeedback, { FeedbackHistory } from './YouTubeFeedback.jsx';
import DownloadedAudio from './DownloadedAudio.jsx';
import VoiceCorrection, { VoiceHistory } from './VoiceCorrection.jsx';
import SessionWizard from './SessionWizard.jsx';
import { secondsRemaining } from '../session-clock.mjs';
import { newId, setToken, request } from '../api/client.js';
import './youtube-demo.css';

const base = '/backend/catalogo/youtube';
export default function YouTubeAutomatic() {
  const [user, setUser] = useState(null);
  if (!user) return <main className="access-wrap"><div><Acceso onAccess={setUser} /><p className="youtube-shortcut">Accede para utilizar tus preferencias y buscar automáticamente las canciones recomendadas.</p><p className="youtube-shortcut"><a href="/?prueba=youtube">Prueba manual sin cuenta</a></p></div></main>;
  return <AutomaticList key={user._id} user={user} logout={() => { setToken(''); setUser(null); }} />;
}

export function AutomaticList({ user, logout, audioOnly = false, embedded = false, sidePanel = null }) {
  const [minutes, setMinutes] = useState(5), [startedAt, setStartedAt] = useState(null), [remaining, setRemaining] = useState(300), [expired, setExpired] = useState(false);
  const deadline = useRef(null);
  const [activity, setActivity] = useState('lectura_comprensiva'), [sessionEnergy, setSessionEnergy] = useState('mantener');
  const [failed, setFailed] = useState({}), [volume, setVolume] = useState(.4);
  const [played, setPlayed] = useState({}), [playbackError, setPlaybackError] = useState('');
  const playbackRequests = useRef(new Set());
  const [cfg, setCfg] = useState(null), [consent, setConsent] = useState(false), [rec, setRec] = useState(null), [selected, setSelected] = useState(null), [index, setIndex] = useState(-1), [status, setStatus] = useState(''), [busy, setBusy] = useState(false), [autoplay, setAutoplay] = useState(false), [skipped, setSkipped] = useState([]);
  const operation = useRef(newId()), lock = useRef(false), alive = useRef(true), generation = useRef(0);
  useEffect(() => { alive.current = true; request(base + '/configuracion').then(setCfg).catch(e => setStatus(e.message)); return () => { alive.current = false; generation.current++; }; }, []);
  useEffect(() => {
    if (startedAt === null || expired) return;
    function tick() {
      const left = secondsRemaining(startedAt, minutes); setRemaining(left);
      if (!left) { deadline.current = 0; generation.current++; setExpired(true); setSelected(null); setStatus('Sesión finalizada: se alcanzó la duración elegida.'); }
    }
    tick(); const timer = setInterval(tick, 500); return () => clearInterval(timer);
  }, [startedAt, minutes, expired]);
  async function findNext(list, start, automatic) {
    const run = generation.current;
    for (let i = start; i < list.canciones.length; i++) {
      if (!alive.current || generation.current !== run || deadline.current === 0) return;
      const song = list.canciones[i]; setIndex(i); setStatus(`Buscando en YouTube: ${song.name || song.track_id}…`);
      if (audioOnly) {
        const feedback = await request(`${base}/recomendaciones/${list._id}/feedback?track_id=${encodeURIComponent(song.track_id)}`);
        if (!alive.current || generation.current !== run) return;
        setSelected({...feedback,titulo_youtube:'Audio bajo demanda',canal:'Caché del servidor'}); setAutoplay(automatic); setStatus('Canción seleccionada.'); return;
      }
      const result = await request(`${base}/recomendaciones/${list._id}/resolver`, { method: 'POST', body: { track_id: song.track_id } });
      if (!alive.current || generation.current !== run) return;
      if (result.estado === 'disponible') { setIndex(i); setSelected(result); setAutoplay(automatic); setStatus('Coincidencia probable encontrada automáticamente. Comprueba la grabación en el reproductor.'); return; }
      setSkipped(items => [...items, `${song.name}: ${result.motivo}`]);
    }
    setSelected(null); setIndex(list.canciones.length); setStatus(audioOnly ? 'La lista ha terminado. Puedes elegir una canción o preparar otra lista.' : 'No quedan canciones con coincidencia probable en esta lista. No se eligieron videos al azar.');
  }
  async function start(answers = null) {
    if (answers?.actividad) { operation.current = newId(); setActivity(answers.actividad); setSessionEnergy(answers.energia_sesion); setMinutes(answers.duracion_minutos); setRemaining(answers.duracion_minutos*60); }
    const activityValue = answers?.actividad || activity, energyValue = answers?.energia_sesion || sessionEnergy, durationValue = answers?.duracion_minutos || minutes;
    if (lock.current || !consent) return; lock.current = true; setBusy(true);
    try {
      const config = await request(base + '/configuracion'); setCfg(config);
      if (!audioOnly && !config.configurado) throw new Error('Falta YOUTUBE_API_KEY en el backend. Añádela al .env del backend y recrea recomendación; nunca la pegues aquí.');
      const list = rec || await request(base + '/recomendaciones', { method: 'POST', body: { solicitud_id: operation.current, limite: 5, modo: audioOnly ? 'audio' : 'youtube', actividad: activityValue, energia_sesion: energyValue, duracion_minutos: durationValue } });
      if (!alive.current) return; setRec(list); await findNext(list, Math.max(0, index), false);
    } catch (e) { if (alive.current) setStatus(e.message); if (answers?.actividad) throw e; } finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  async function next(reason) {
    return goTo(index + 1, reason);
  }
  async function goTo(position, reason) {
    if (lock.current || !rec || !consent || expired || deadline.current === 0) return; lock.current = true; setBusy(true); setSelected(null);
    generation.current++;
    if (reason) setSkipped(items => [...items, reason]);
    try { await findNext(rec, Math.max(0, position), true); } catch (e) { if (alive.current) setStatus(e.message); } finally { lock.current = false; if (alive.current) setBusy(false); }
  }
  function skipUnavailable(message) {
    if (!song) return;
    setFailed(items => ({...items,[song.track_id]:true}));
    void next(`${song.name}: no disponible. ${message}`);
  }
  async function registerPlayback() {
    if (!rec || !selected || !song) return;
    if (deadline.current === 0) { setSelected(null); return; }
    if (deadline.current === null) { const startTime = Date.now(); deadline.current = startTime + minutes * 60000; setStartedAt(startTime); }
    const key = `${rec._id}:${song.track_id}`;
    if (played[key] || playbackRequests.current.has(key)) return;
    playbackRequests.current.add(key);
    try {
      const event = await request(`${base}/recomendaciones/${rec._id}/reproduccion`, { method: 'POST', body: { track_id: song.track_id } });
      if (event.inicio_web && alive.current) { const timestamp = Date.parse(event.inicio_web); setStartedAt(timestamp); if (deadline.current !== 0) deadline.current = timestamp + minutes * 60000; }
      if (alive.current) { setPlayed(items => ({ ...items, [key]: true })); setPlaybackError(''); }
    } catch (e) { if (alive.current) setPlaybackError(`No se pudo registrar la reproducción: ${e.message}. Pausa y vuelve a reproducir para reintentar.`); }
    finally { playbackRequests.current.delete(key); }
  }
  const song = rec?.canciones[index];
  const navigation = rec && <div className="youtube-actions" aria-label="Controles de la lista"><button disabled={busy || !consent || expired || index<=0} onClick={() => goTo(index-1)}>Canción anterior</button><button disabled={busy || !consent || expired || index>=rec.canciones.length-1} onClick={() => next('Canción omitida por el usuario; no implica rechazo musical.')}>Siguiente canción</button></div>;
  function resetList() {
    generation.current++; operation.current = newId(); deadline.current=null;setStartedAt(null);setExpired(false);setRemaining(minutes*60);setSelected(null);setRec(null);setIndex(-1);setSkipped([]);setFailed({});setStatus('Puedes preparar otra sesión.');
  }
  if (embedded) return <section className="music-desk" id="audio-web" aria-label="Espacio de reproducción musical">
    <aside className="music-library">
      <div className="eyebrow">SESIÓN DE ESTUDIO</div><h2>Tu lista</h2>
      {!rec ? <p>Las canciones aparecerán aquí cuando prepares tu sesión.</p> : <>
        <p id="sesion" className="session-remaining" role="timer" aria-live="off">{expired ? 'Sesión finalizada' : startedAt === null ? `${minutes} minutos` : `${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')} restantes`}</p>
        <ol className="music-queue" aria-label="Lista de reproducción">{rec.canciones.map((item,i)=><li key={item.track_id}><button disabled={busy || !consent || expired} aria-current={index===i ? 'true' : undefined} onClick={()=>goTo(i)}><span className="queue-position">{index===i && selected ? '▶' : String(i+1).padStart(2,'0')}</span><span><strong>{item.name}</strong><small>{item.artists?.join(', ')}{failed[item.track_id] ? ' · No disponible' : ''}</small></span></button></li>)}</ol>
        <div className="library-actions"><button disabled={busy || expired} onClick={()=>start()}>Reintentar canción</button><button disabled={busy} onClick={resetList}>Preparar otra sesión</button></div>
      </>}
      <details className="library-history"><summary>Mi historial</summary><FeedbackHistory /><VoiceHistory /></details>
    </aside>
    <div className="music-stage">
      <div className="eyebrow">{selected && !expired ? 'AHORA SUENA' : 'REPRODUCTOR'}</div>
      {rec ? <>
        <div className="now-playing-art" aria-hidden="true">♫</div>
        <h2 className="now-playing-title">{song?.name || (expired ? 'Sesión finalizada' : 'Lista completada')}</h2>
        <p className="now-playing-artist">{song?.artists?.join(', ') || 'Puedes preparar otra sesión cuando quieras.'}</p>
        {song && <p className="track-position">Canción {index+1} de {rec.canciones.length}</p>}
        <p role="status" className="stage-status">{status}</p>
        {selected && song ? <>
          {audioOnly ? <DownloadedAudio key={`${rec._id}:${song.track_id}`} rec={rec} song={song} autoplay={autoplay} onPlaying={registerPlayback} onEnded={()=>next()} onUnavailable={skipUnavailable} volume={volume} onVolumeChange={setVolume} /> : <OfficialYouTubePlayer key={`${rec._id}:${song.track_id}:${selected.video_id}`} videoId={selected.video_id} autoplay={autoplay} onPlaying={registerPlayback} onEnded={()=>next()} onUnavailable={skipUnavailable} />}
          {navigation}<button className="stage-stop" onClick={()=>{generation.current++;setSelected(null);setStatus('Reproducción detenida.');}}>Detener reproducción</button>
          <div className="stage-feedback"><YouTubeFeedback key={`${rec._id}:${song.track_id}`} recommendationId={rec._id} song={song} result={selected} played={!!played[`${rec._id}:${song.track_id}`]} /></div>
        </> : navigation}
        {playbackError && <p role="alert">{playbackError}</p>}
      </> : <div className="player-welcome"><div className="now-playing-art" aria-hidden="true">♫</div><h2>Tu música para estudiar</h2><p>Prepara una sesión y escucha tu selección aquí.</p><SessionWizard onComplete={start} disabled={busy} consent={consent} onConsentChange={setConsent} /><p role="status">{status}</p></div>}
    </div>
    <aside className="music-settings">{sidePanel}
      {song && <details className="track-info"><summary>Sobre esta recomendación</summary>
        {song.desglose_puntaje && <><p>Compatibilidad: {song.puntaje_compatibilidad.toFixed(1)}/100. No mide concentración.</p><ul>{Object.entries(song.desglose_puntaje).map(([key,part])=><li key={key}>{{gustos:'Gustos',voz:'Voz',tempo:'Ritmo',energy:'Energía'}[key]}: {part.aporte_puntos.toFixed(1)} puntos</li>)}</ul></>}
        <VoiceCorrection key={`voice:${rec._id}:${song.track_id}`} recommendationId={rec._id} song={song} played={!!played[`${rec._id}:${song.track_id}`]} />
      </details>}
      {rec?.aviso_seleccion && <p>{rec.aviso_seleccion}</p>}
      {skipped.length>0 && <details className="track-info"><summary>Canciones no disponibles ({skipped.length})</summary><ul>{skipped.map((s,i)=><li key={i}>{s}</li>)}</ul></details>}
      <p className="room-note">La actividad se realiza en la sala virtual. Aquí se reproduce la música.</p>
    </aside>
  </section>;
  const Wrapper = embedded ? 'section' : 'main';
  return <Wrapper className="youtube-page" id={embedded ? 'audio-web' : undefined}>{!embedded && <header className="youtube-header"><a href="/">StudySpace VR</a><span>YouTube · Selección automática</span><button onClick={logout}>Salir</button></header>}<section className="youtube-card"><div className="eyebrow">{embedded ? '01 / SESIÓN' : 'MÚSICA'}</div><h2>{embedded ? 'Tu sesión de estudio' : 'Tu música'}</h2><p>{embedded ? 'Configura la actividad y la música en una ventana independiente.' : 'Prepara una lista con tus preferencias musicales.'}</p>
    {!embedded && <label className="youtube-consent"><input type="checkbox" checked={consent} onChange={e => { setConsent(e.target.checked); if (!e.target.checked) { generation.current++; setSelected(null); setStatus('Conexión retirada; reproductor detenido.'); } }} />Permitir búsquedas y reproducción con YouTube en esta vista web. Se enviarán títulos y artistas, no mi perfil, encuestas ni credenciales.</label>}
    {!embedded && audioOnly && <p>El audio se prepara al elegir una canción y se guarda para próximas reproducciones. Utiliza material que tengas permiso de descargar y reutilizar.</p>}
    {!audioOnly && <details className="youtube-privacy"><summary>Privacidad y condiciones de esta conexión</summary><p>Esta vista utiliza YouTube Data API y su reproductor oficial. El backend envía títulos y artistas; Google recibe además las solicitudes de reproducción del navegador. Las asociaciones temporales se conservan hasta siete días. No se solicitan credenciales de Google. Se aplican los <a href="https://www.youtube.com/t/terms" target="_blank" rel="noreferrer">Términos de YouTube</a> y la <a href="https://policies.google.com/privacy" target="_blank" rel="noreferrer">Política de privacidad de Google</a>.</p></details>}
    {!embedded && <details className="youtube-privacy"><summary>Revisar mis preferencias musicales antes de recomendar</summary><div className="integrated-shell"><Preferencias locked={busy || !!rec} /></div></details>}
    {!audioOnly && cfg && !cfg.configurado && <div className="youtube-error" role="alert">La búsqueda automática está preparada, pero falta configurar YOUTUBE_API_KEY en el backend.</div>}
    {embedded && !rec && <SessionWizard onComplete={start} disabled={busy} consent={consent} onConsentChange={setConsent} />}
    {!embedded && <fieldset disabled={busy || !!rec}><legend>Prepara tu sesión</legend>
      <label>¿Qué actividad vas a realizar?<select value={activity} onChange={e => { setActivity(e.target.value); operation.current = newId(); }}><option value="lectura_comprensiva">Lectura comprensiva</option><option value="atencion_flechas">Atención visual con flechas</option></select></label>
      <label>¿Cómo prefieres que sea la música durante esta sesión?<select value={sessionEnergy} onChange={e => { setSessionEnergy(e.target.value); operation.current = newId(); }}><option value="mantener">Mantener mis preferencias</option><option value="suave">Suave y tranquila</option><option value="energica">Con mayor energía</option></select></label>
      <p>La actividad se realiza en la sala virtual. Aquí preparamos su música.</p>
      <label>Duración de la sesión<select value={minutes} onChange={e=>{setMinutes(Number(e.target.value));operation.current=newId();}}>{Array.from({length:8},(_,i)=>i+3).map(n=><option key={n} value={n}>{n} minutos</option>)}</select></label>
    </fieldset>}
    <div className="youtube-actions">{(!embedded || rec) && <button disabled={!consent || busy || expired} onClick={()=>start()}>{busy ? 'Preparando…' : rec ? 'Reintentar canción actual' : 'Preparar mi lista'}</button>}{selected && <button onClick={() => { generation.current++; setSelected(null); setStatus('Reproducción detenida.'); }}>Detener</button>}</div>
    {rec && <p id="sesion" role="timer" aria-live="off">{expired ? 'Sesión finalizada' : startedAt === null ? `Duración: ${minutes} minutos. El tiempo comienza al reproducir.` : `Tiempo restante: ${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')}`}. Las pausas no reinician el tiempo.</p>}
    <p role="status">{status}</p>
    {rec?.preseleccion_voz?.preferencia && <p>Preselección por instrumentalidad estimada del catálogo. No se ha verificado la voz ni la letra del audio.</p>}
    {rec?.aviso_seleccion && <p role="status">{rec.aviso_seleccion}</p>}
    {song && <VoiceCorrection key={`voice:${rec._id}:${song.track_id}`} recommendationId={rec._id} song={song} played={!!played[`${rec._id}:${song.track_id}`]} />}
    {rec?.normalizacion_generos && <p>Géneros utilizados: {rec.perfil_utilizado.generos_preferidos.join(', ') || 'sin coincidencias de género'}.{rec.normalizacion_generos.no_reconocidos.length > 0 && ` No se reconocieron: ${rec.normalizacion_generos.no_reconocidos.join(', ')}. Revisa las sugerencias del perfil y prepara otra lista.`}</p>}
    {rec && <><button disabled={busy} onClick={() => { generation.current++; operation.current = newId(); deadline.current=null;setStartedAt(null);setExpired(false);setRemaining(minutes*60);setSelected(null); setRec(null); setIndex(-1); setSkipped([]);setFailed({}); setStatus('Lista cerrada en esta vista. Puedes preparar otra sesión; no se borraron registros.'); }}>Preparar una nueva lista</button><details className="youtube-privacy" open><summary>Lista de reproducción · {rec.canciones.length} canciones</summary><ol aria-label="Lista de reproducción">{rec.canciones.map((item,i)=><li key={item.track_id}><button disabled={busy || !consent || expired} aria-current={index===i ? 'true' : undefined} onClick={()=>goTo(i)}>{index===i ? '▶ ' : ''}{item.name} · {item.artists?.join(', ')}{failed[item.track_id] ? ' · No disponible' : ''}</button></li>)}</ol></details></>}
    {!selected && navigation}
    {song?.desglose_puntaje && <details><summary>¿Por qué se recomienda esta canción?</summary><p>Compatibilidad con tus respuestas: {song.puntaje_compatibilidad.toFixed(1)}/100. No es una medida de concentración.</p><ul>{Object.entries(song.desglose_puntaje).map(([key, part]) => <li key={key}>{{gustos:'Artistas y géneros',voz:'Instrumental o con voz',tempo:'Ritmo',energy:'Energía'}[key]}: {part.aporte_puntos.toFixed(1)} puntos · peso {(part.peso_aplicado*100).toFixed(0)} %{part.coincidencia === null ? ' · dato del catálogo ausente' : ''}</li>)}</ul></details>}
    {selected && song && <><h2>{song.name}</h2><p>{song.artists?.join(', ')} · Canción {index + 1}/{rec.canciones.length}</p>{navigation}{audioOnly ? <DownloadedAudio key={`${rec._id}:${song.track_id}`} rec={rec} song={song} autoplay={autoplay} onPlaying={registerPlayback} onEnded={() => next()} onUnavailable={skipUnavailable} volume={volume} onVolumeChange={setVolume} /> : <><p>Video encontrado: <strong>{selected.titulo_youtube}</strong> · Canal: {selected.canal}</p><p>Coincidencia probable por metadatos; no verificación acústica de la misma grabación.</p><OfficialYouTubePlayer key={`${rec._id}:${song.track_id}:${selected.video_id}`} videoId={selected.video_id} autoplay={autoplay} onPlaying={registerPlayback} onEnded={() => next()} onUnavailable={skipUnavailable} /></>}<YouTubeFeedback key={`${rec._id}:${song.track_id}`} recommendationId={rec._id} song={song} result={selected} played={!!played[`${rec._id}:${song.track_id}`]} />{playbackError && <p role="alert">{playbackError}</p>}</>}
    {skipped.length > 0 && <details className="youtube-privacy"><summary>Resultados omitidos ({skipped.length})</summary><ul>{skipped.map((item, i) => <li key={i}>{item}</li>)}</ul></details>}
    <details className="personal-history"><summary>Mi historial</summary><FeedbackHistory /><VoiceHistory /></details>
    <aside className="youtube-note">{embedded ? 'La actividad se realiza en la sala virtual. Aquí se prepara y reproduce la música.' : 'El primer inicio puede requerir pulsar Reproducir. Solo las valoraciones explícitas ajustan tus gustos.'}</aside>
  </section></Wrapper>;
}

import React, { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { getProfile, saveProfile } from '../api/usuarios.js';
import { artists } from '../api/recomendaciones.js';
import { request } from '../api/client.js';

const titles = ['¿Qué actividad vas a realizar?', '¿Cuánto durará tu sesión?', '¿Qué géneros musicales prefieres para estudiar?', '¿Qué artistas te gustaría escuchar mientras estudias?', 'Para estudiar, ¿prefieres música instrumental o con voz?', '¿Qué ritmo musical prefieres mientras estudias?', '¿Cómo prefieres que sea la música durante esta sesión?'];
const tempos = ['lento','moderado','rapido'];
const tempoLabels = ['Lento','Moderado','Rápido'];
function Choices({ name, value, onChange, options }) {
  return <div className="question-choices" role="radiogroup" aria-label={name}>{options.map(([id,label,description])=><label key={id} className="question-choice"><input type="radio" name={name} value={id} checked={value===id} onChange={()=>onChange(id)} /><span><strong>{label}</strong>{description && <small>{description}</small>}</span><span className="choice-mark" aria-hidden="true">{value===id ? '✓' : ''}</span></label>)}</div>;
}
export default function SessionWizard({ onComplete, disabled = false, consent = false, onConsentChange }) {
  const dialog = useRef(null), trigger = useRef(null);
  const [open, setOpen] = useState(false), [step, setStep] = useState(0), [profile, setProfile] = useState(null);
  const [activity, setActivity] = useState('lectura_comprensiva'), [minutes, setMinutes] = useState(5), [energy, setEnergy] = useState('mantener');
  const [genres, setGenres] = useState(''), [selected, setSelected] = useState([]), [voice, setVoice] = useState(''), [tempo, setTempo] = useState('');
  const [search, setSearch] = useState(''), [rows, setRows] = useState([]), [suggestions, setSuggestions] = useState([]), [names, setNames] = useState({});
  const [busy, setBusy] = useState(false), [loadingArtists, setLoadingArtists] = useState(false), [error, setError] = useState('');
  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    if (!dialog.current.open) dialog.current.showModal();
    return () => { document.body.style.overflow = previous; trigger.current?.focus(); };
  }, [open]);
  useEffect(() => {
    if (open) (dialog.current?.querySelector('input:checked') || dialog.current?.querySelector('select, input'))?.focus();
  }, [open, step]);
  useEffect(() => {
    if (!open || step !== 3) return;
    let alive = true; setLoadingArtists(true);
    const timer = setTimeout(() => artists(1, search).then(items => { if (alive) { setRows(items); setNames(prev => ({...prev,...Object.fromEntries(items.map(a => [a.id,a.name]))})); } }).catch(e => alive && setError(e.message)).finally(()=>{if(alive)setLoadingArtists(false);}), 250);
    return () => { alive = false; clearTimeout(timer); };
  }, [open, step, search]);
  useEffect(() => {
    if (!open || step !== 2) return;
    let alive = true;
    const timer = setTimeout(() => request('/backend/catalogo/catalogo/generos?q=' + encodeURIComponent(genres.split(',').at(-1).trim())).then(items => alive && setSuggestions(items)).catch(e => alive && setError(e.message)),250);
    return () => { alive = false; clearTimeout(timer); };
  }, [open, step, genres]);
  async function begin() {
    setBusy(true); setError('');
    try { const p = await getProfile(); setProfile(p); setGenres(p.generos_preferidos.join(', ')); setSelected(p.artistas_preferidos); setVoice(p.preferencia_voz || ''); setTempo(p.tempo_preferido || ''); if(p.artistas_preferidos.length) { const saved = await artists(1,'',p.artistas_preferidos);setNames(prev=>({...prev,...Object.fromEntries(saved.map(a=>[a.id,a.name]))})); } setStep(0); setOpen(true); }
    catch(e) { setError(e.message); } finally { setBusy(false); }
  }
  async function advance(e) {
    e.preventDefault(); setError('');
    const list = [...new Set(genres.split(',').map(x => x.trim()).filter(Boolean))];
    if ((step === 2 && list.length > 3) || (step === 3 && selected.length > 3)) { setError('Selecciona hasta tres opciones.'); return; }
    if (step < titles.length - 1) { setStep(step + 1); return; }
    if (!consent) { setError('Autoriza la búsqueda y reproducción para preparar tu música.'); return; }
    setBusy(true);
    try {
      const p = await saveProfile({version_esperada:profile.version, artistas_preferidos:selected, generos_preferidos:list, preferencia_voz:voice || null, tempo_preferido:tempo || null});
      setProfile(p); setGenres(p.generos_preferidos.join(', '));
      await onComplete({actividad:activity, duracion_minutos:minutes, energia_sesion:energy});
      setOpen(false);
    } catch(e) {
      setError(e.message);
      if(e.status === 409) { const p = await getProfile().catch(() => null); if(p) setProfile(p); }
    } finally { setBusy(false); }
  }
  const launcher = <div id="sesion" className="session-launch"><button ref={trigger} className="primary-btn" disabled={disabled || busy} onClick={begin}>{busy ? 'Cargando…' : 'Preparar sesión'}<span aria-hidden="true">↗</span></button><p>De 3 a 10 minutos · Puedes revisar tus preferencias.</p>{!open && error && <p role="alert">{error}</p>}</div>;
  return <>{launcher}{open && createPortal(<dialog ref={dialog} className="study-dialog" aria-labelledby="session-question" onCancel={e=>{e.preventDefault();if(!busy)setOpen(false);}}>
    <header className="dialog-header"><span>Preparar sesión</span><button type="button" aria-label="Cerrar preparación" disabled={busy} onClick={()=>setOpen(false)}>×</button></header>
    <div className="dialog-progress"><span>Paso {step + 1} de {titles.length}</span><div aria-hidden="true">{titles.map((_,i)=><i key={i} className={i<=step ? 'complete' : ''} />)}</div></div>
    <form onSubmit={advance}><fieldset disabled={busy || disabled}><legend><h2 id="session-question">{titles[step]}</h2></legend><div className="dialog-fields">
      {step === 0 && <Choices name="Actividad" value={activity} onChange={setActivity} options={[["lectura_comprensiva","Lectura comprensiva","Leer un texto y responder preguntas."],["atencion_flechas","Atención visual con flechas","Identificar la dirección de la flecha central."]]} />}
      {step === 1 && <><p>Elige entre 3 y 10 minutos.</p><div className="duration-options" role="radiogroup" aria-label="Duración de la sesión">{Array.from({length:8},(_,i)=>i+3).map(n=><label className="duration-option" key={n}><input type="radio" name="duration" checked={minutes===n} onChange={()=>setMinutes(n)} /><strong>{n}</strong><span>min</span></label>)}</div></>}
      {step === 2 && <><label>Géneros (hasta tres, separados por comas)<input value={genres} maxLength={300} onChange={e=>setGenres(e.target.value)} /></label><button type="button" onClick={()=>setGenres('')}>No tengo preferencia</button><div className="button-row">{suggestions.slice(0,8).map(g=><button type="button" key={g.id} onClick={()=>{const parts=genres.split(',').map(x=>x.trim());parts.pop();setGenres([...parts.filter(Boolean),g.id].join(', '));}}>{g.nombre}</button>)}</div></>}
      {step === 3 && <><p>Opcional · Elige hasta tres artistas ({selected.length}/3).</p><label>Buscar artistas<input value={search} placeholder="Nombre del artista" maxLength={100} onChange={e=>setSearch(e.target.value)} /></label>
        {selected.length>0 && <div className="selected-artists" aria-label="Artistas seleccionados">{selected.map(id=><button type="button" key={id} aria-label={`Quitar ${names[id] || 'artista guardado'}`} onClick={()=>setSelected(prev=>prev.filter(x=>x!==id))}>{names[id] || 'Artista guardado'}<span aria-hidden="true">×</span></button>)}</div>}
        <div className="artist-bubbles" aria-label="Resultados de artistas">{rows.map(a=><button type="button" className="artist-bubble" key={a.id} aria-pressed={selected.includes(a.id)} disabled={!selected.includes(a.id) && selected.length>=3} onClick={()=>setSelected(prev=>prev.includes(a.id) ? prev.filter(x=>x!==a.id) : [...prev,a.id])}><span className="artist-monogram" aria-hidden="true">{a.name.split(/\s+/).slice(0,2).map(x=>x[0]).join('')}<i>{selected.includes(a.id) ? '✓' : '+'}</i></span><span>{a.name}</span></button>)}</div>{loadingArtists ? <p role="status">Buscando artistas…</p> : !rows.length && <p>No hay artistas para mostrar. Prueba otro nombre.</p>}</>}
      {step === 4 && <Choices name="Preferencia de voz" value={voice} onChange={setVoice} options={[["instrumental","Instrumental","Prefiero música sin voz."],["con_voz","Con voz","Prefiero canciones con voz."],["","Sin preferencia","Cualquiera de las dos opciones."]]} />}
      {step === 5 && <div className="tempo-control"><div className="tempo-value"><span>Ritmo preferido</span><strong>{tempo ? tempoLabels[tempos.indexOf(tempo)] : 'Sin preferencia'}</strong></div><input aria-label="Ritmo musical" aria-valuetext={tempo ? tempoLabels[tempos.indexOf(tempo)] : 'Sin preferencia'} type="range" onClick={e=>setTempo(tempos[Number(e.currentTarget.value)])} min="0" max="2" step="1" value={tempo ? tempos.indexOf(tempo) : 1} onChange={e=>setTempo(tempos[Number(e.target.value)])} /><div className="tempo-labels">{tempos.map((t,i)=><button type="button" key={t} aria-pressed={tempo===t} onClick={()=>setTempo(t)}>{tempoLabels[i]}</button>)}</div><button type="button" className="no-tempo" aria-pressed={!tempo} onClick={()=>setTempo('')}>Sin preferencia</button></div>}
      {step === 6 && <Choices name="Energía de la música" value={energy} onChange={setEnergy} options={[["suave","Suave y tranquila","Menor energía musical."],["energica","Con mayor energía","Un acompañamiento más enérgico."],["mantener","Mantener mis preferencias","Usar mi perfil guardado."]]} />}
      {step === 6 && <label className="dialog-consent"><input type="checkbox" checked={consent} onChange={e=>onConsentChange?.(e.target.checked)} /><span>Permitir buscar y reproducir música con YouTube. Solo se envían títulos y artistas.</span></label>}
      </div><div className="dialog-footer"><button type="button" disabled={step===0} onClick={()=>{setError('');setStep(step-1);}}>Anterior</button><button type="submit" className="primary-btn">{busy ? 'Preparando…' : step===6 ? 'Preparar música' : 'Continuar'}<span aria-hidden="true">→</span></button></div>
    </fieldset></form>{error && <p role="alert">{error}</p>}
  </dialog>,document.body)}</>;
}

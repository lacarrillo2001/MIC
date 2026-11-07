import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity, ArrowRight, AudioLines, BookOpenText, Check, ChevronRight, CircleHelp, Clock3,
  CloudSun, Coffee, Headset, Lightbulb, Menu, MonitorPlay, MoonStar, Music2, Pause,
  Play, Radio, Settings2, ShieldCheck, SlidersHorizontal, Sparkles, Sun, Volume2,
  VolumeX, Waves, Wifi, WifiOff, X
} from 'lucide-react';

const defaultState = {
  brightness: 1.25, lightingPreset:'neutro', musicStyle:'ambiental', volume:42,
  focusMinutes:25, sessionActive:false, sessionStartedAt:null, vrConnected:false
};
const presets = [
  {id:'calido',label:'Cálida',desc:'Relajante',icon:Sun},
  {id:'neutro',label:'Neutra',desc:'Equilibrada',icon:CloudSun},
  {id:'frio',label:'Fría',desc:'Energizante',icon:MoonStar},
];
const tracks = [
  {id:'ambiental',label:'Ambiental',subtitle:'Sonidos suaves',glyph:'◌'},
  {id:'clasica',label:'Clásica',subtitle:'Instrumental',glyph:'♫'},
  {id:'lofi',label:'Lo-fi',subtitle:'Ritmo relajado',glyph:'≋'},
  {id:'naturaleza',label:'Naturaleza',subtitle:'Sonidos naturales',glyph:'✳'},
  {id:'silencio',label:'Sin música',subtitle:'Concentración en silencio',glyph:'○'},
];
const nav=[
  {id:'inicio',label:'Inicio',icon:Activity},
  {id:'ambiente',label:'Mi ambiente',icon:Lightbulb},
  {id:'musica',label:'Música',icon:Music2},
  {id:'sesion',label:'Sesión de estudio',icon:Clock3},
  {id:'dispositivo',label:'Dispositivo VR',icon:Headset}
];
function formatSeconds(n){ const v=Math.max(0,Math.floor(n));return `${String(Math.floor(v/60)).padStart(2,'0')}:${String(v%60).padStart(2,'0')}`;}
function Tag({children,online=false}){return <span className={'pill '+(online?'online':'')}><span className="small-dot"/>{children}</span>}
function CardHeader({eyebrow,title,subtitle,action}){
 return <div className="panel-title-area"><div><div className="eyebrow">{eyebrow}</div><h2>{title}</h2>{subtitle&&<p>{subtitle}</p>}</div>{action}</div>
}
function RoomPreview(){return <div className="room-preview" aria-label="Ilustración conceptual de la sala; no es una captura en tiempo real de Unreal">
  <div className="preview-glow"/><div className="back-wall"><div className="window-frame"><div className="sky-gradient"><span className="view-hill one"/><span className="view-hill two"/></div><div className="window-cross"/></div><div className="art-frame"><span/></div></div>
  <div className="side-wall"/><div className="preview-floor"/><div className="preview-rug"/><div className="preview-desk"><div className="desk-surface"/><div className="desk-leg l"/><div className="desk-leg r"/><div className="screen"><div/></div><div className="screen-neck"/><div className="keyboard"/></div><div className="chair-back"/><div className="chair-seat"/><div className="plant"><div className="leaf a"/><div className="leaf b"/><div className="leaf c"/><div className="leaf d"/><div className="pot"/></div>
  <div className="floating-cue"><span className="cue-circle"><Sparkles size={14}/></span>Ambiente de estudio</div><span className="mock-label">Vista ilustrativa</span>
 </div>}

export default function App(){
 const [state,setState]=useState(defaultState);
 const [active,setActive]=useState('inicio');
 const [mobileOpen,setMobileOpen]=useState(false);
 const [loaded,setLoaded]=useState(false);
 const [error,setError]=useState('');
 const [busy,setBusy]=useState(false);
 const [sliderBrightness,setSliderBrightness]=useState(1.25);
 const [sliderVolume,setSliderVolume]=useState(42);
 const [now,setNow]=useState(Date.now());
 const [demoPlaying,setDemoPlaying]=useState(false);
 const audioRef=useRef(null);
 const load=useCallback(async()=>{
   try { const res=await fetch('/api/state',{cache:'no-store'});if(!res.ok)throw new Error('No se pudo consultar la API');
     const data=await res.json();setState(data);setSliderBrightness(data.brightness);setSliderVolume(data.volume);setLoaded(true);setError('');
   } catch(e){setError('El servicio local no responde. Inicia el puente Node de la carpeta bridge.');setLoaded(true);}
 },[]);
 useEffect(()=>{load();const poll=setInterval(load,3500);const clock=setInterval(()=>setNow(Date.now()),1000);return()=>{clearInterval(poll);clearInterval(clock)}},[load]);
 useEffect(()=>{if(audioRef.current)audioRef.current.volume=Math.min(1,Math.max(0,state.volume/100));},[state.volume]);
 const change=async(patch)=>{
    setBusy(true);
    try {const response=await fetch('/api/state',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify(patch)});
      const data=await response.json();if(!response.ok)throw new Error(data.error||'Error al actualizar');
      setState(data);setError('');return true;
    }catch(e){setError(e.message);return false;}finally{setBusy(false)}
 };
 const select=(id)=>{setActive(id);setMobileOpen(false);document.getElementById(id)?.scrollIntoView({behavior:'smooth',block:'start'});};
 const previewMusic=async()=>{
   if(!audioRef.current)return;
   if(demoPlaying){audioRef.current.pause();setDemoPlaying(false);return;}
   try{audioRef.current.volume=sliderVolume/100;await audioRef.current.play();setDemoPlaying(true)}catch{setError('El navegador bloqueó la reproducción. Vuelve a pulsar Reproducir.')}
 };
 const remaining=state.sessionActive&&state.sessionStartedAt?
   Math.max(0,state.focusMinutes*60-Math.floor((now-Date.parse(state.sessionStartedAt))/1000)):state.focusMinutes*60;
 const currentTrack=tracks.find(t=>t.id===state.musicStyle)||tracks[0];
 return <div className="layout">
   <audio ref={audioRef} src="/ambient-demo.wav" loop preload="none" onEnded={()=>setDemoPlaying(false)}/>
   <aside className={'sidebar '+(mobileOpen?'sidebar-open':'')}>
     <div className="brand"><div className="brand-mark"><span className="brand-mark-inner"/></div><div>StudySpace <strong>VR</strong><small>ESPACIO DE CONCENTRACIÓN</small></div><button className="mobile-close" onClick={()=>setMobileOpen(false)} aria-label="Cerrar menú"><X size={18}/></button></div>
     <div className="side-section-label">ESPACIO DE TRABAJO</div>
     <nav aria-label="Secciones principales">{nav.map(item=><button key={item.id} onClick={()=>select(item.id)} className={'nav-button '+(active===item.id?'selected':'')}><item.icon size={19} strokeWidth={1.9}/>{item.label}{item.id===active&&<span className="nav-bar"/>}</button>)}</nav>
     <div className="side-promo"><div className="promo-icon"><Headset size={20}/></div><strong>Tu espacio inmersivo</strong><p>Configura tu sala desde aquí y experimenta el ambiente con tus gafas VR.</p><button onClick={()=>select('dispositivo')}>Ver conexión <ArrowRight size={15}/></button></div>
     <div className="sidebar-bottom"><span className={'connection-dot '+(state.vrConnected?'connected':'')}/><div><strong>{state.vrConnected?'Unreal conectado':'Unreal desconectado'}</strong><small>Comunicación local</small></div></div>
   </aside>
   {mobileOpen&&<button className="scrim" onClick={()=>setMobileOpen(false)} aria-label="Cerrar panel"/>}
   <main className="main-content" id="inicio">
     <header className="topbar"><button className="menu-button" onClick={()=>setMobileOpen(true)} aria-label="Abrir menú"><Menu size={21}/></button><span className="breadcrumb">Panel de control <ChevronRight size={15}/> <b>Mi espacio</b></span><div className="top-right"><span className="top-chip"><ShieldCheck size={15}/> Sesión local</span><span className="avatar">S</span></div></header>
     <div className="content-inner">
       <div className="greeting"><div><div className="eyebrow"><span className="tiny-star">✦</span> TU ESPACIO PERSONAL</div><h1>Un lugar para <em>enfocarte.</em></h1><p>Prepara tu entorno, elige la iluminación y comienza una sesión de estudio inmersiva.</p></div><div className="date-pill"><Clock3 size={17}/>{new Intl.DateTimeFormat('es-EC',{weekday:'long',day:'numeric',month:'long'}).format(new Date(now))}</div></div>
       {error&&<div className="error-banner" role="alert"><WifiOff size={17}/>{error}<button onClick={load}>Reintentar</button></div>}
       <section className="hero"><div className="hero-text"><div className="hero-tag"><span/> TU EXPERIENCIA VR</div><h2>Transforma tu forma<br/>de <em>estudiar.</em></h2><p>Un entorno tranquilo, pensado para minimizar distracciones y acompañar tu concentración.</p><div className="hero-actions"><button className="primary-btn" onClick={()=>select('sesion')}><Play size={16} fill="currentColor"/> Configurar sesión</button><button className="ghost-btn" onClick={()=>select('dispositivo')}>Cómo entrar a VR <ArrowRight size={17}/></button></div></div><RoomPreview/></section>
       <div className="overview-row"><div className="overview-item"><div className="overview-icon teal"><Headset size={21}/></div><div><span>Conexión Unreal</span><strong>{state.vrConnected?'En línea':'Sin conexión'}</strong></div></div><div className="overview-item"><div className="overview-icon blue"><Lightbulb size={20}/></div><div><span>Iluminación actual</span><strong>{presets.find(p=>p.id===state.lightingPreset)?.label || 'Cálida'}</strong></div></div><div className="overview-item"><div className="overview-icon lavender"><AudioLines size={21}/></div><div><span>Preferencia musical</span><strong>{currentTrack.label}</strong></div></div><div className="overview-item"><div className="overview-icon amber"><Clock3 size={21}/></div><div><span>Duración elegida</span><strong>{state.focusMinutes} minutos</strong></div></div></div>
       <div className="section-lead"><h2>Personaliza tu experiencia</h2><p>Ajusta cada detalle a tu ritmo antes de comenzar.</p></div>
       <div className="controls-grid">
         <section id="ambiente" className="panel"><CardHeader eyebrow="AMBIENTE" title="Iluminación" subtitle="Crea un ambiente cómodo para estudiar." action={<span className="panel-icon"><Sun size={18}/></span>}/><div className="control-label">Temperatura de luz</div><div className="light-presets">{presets.map(p=><button key={p.id} disabled={busy} className={'preset '+(state.lightingPreset===p.id?'active':'')} onClick={()=>change({lightingPreset:p.id})}><p.icon size={21}/><strong>{p.label}</strong><small>{p.desc}</small></button>)}</div><div className="slider-heading"><label htmlFor="brightness">Intensidad de luz</label><strong>{Math.round(sliderBrightness*100)}%</strong></div><input id="brightness" type="range" min="0.2" max="3" step="0.05" value={sliderBrightness} onChange={e=>setSliderBrightness(Number(e.target.value))} onPointerUp={()=>change({brightness:sliderBrightness})} onKeyUp={()=>change({brightness:sliderBrightness})} onBlur={()=>{if(sliderBrightness!==state.brightness)change({brightness:sliderBrightness})}} style={{'--pct':`${(sliderBrightness-.2)/2.8*100}%`}}/><div className="slider-ends"><span>Tenue</span><span>Brillante</span></div><div className="info-note"><Sparkles size={16}/> Los cambios se aplican en Unreal cuando la escena está en ejecución.</div></section>
         <section id="musica" className="panel"><CardHeader eyebrow="AUDIO" title="Tu música" subtitle="Selecciona un estilo para tu sesión." action={<span className="panel-icon"><Music2 size={18}/></span>}/><div className="music-list">{tracks.map(t=><button disabled={busy} key={t.id} className={'music-choice '+(state.musicStyle===t.id?'active':'')} onClick={()=>change({musicStyle:t.id})}><span className="track-icon">{t.glyph}</span><span><strong>{t.label}</strong><small>{t.subtitle}</small></span>{state.musicStyle===t.id&&<Check size={18}/>}</button>)}</div><div className="volume-line"><Volume2 size={19}/><input aria-label="Volumen de muestra" type="range" min="0" max="100" step="1" value={sliderVolume} onChange={e=>{setSliderVolume(Number(e.target.value));if(audioRef.current)audioRef.current.volume=Number(e.target.value)/100}} onPointerUp={()=>change({volume:sliderVolume})} onKeyUp={()=>change({volume:sliderVolume})} onBlur={()=>{if(sliderVolume!==state.volume)change({volume:sliderVolume})}} style={{'--pct':`${sliderVolume}%`}}/><strong>{sliderVolume}%</strong></div><div className="audio-preview"><button className="preview-btn" onClick={previewMusic}>{demoPlaying?<Pause size={16} fill="currentColor"/>:<Play size={16} fill="currentColor"/>} {demoPlaying?'Pausar muestra':'Escuchar muestra'}</button><span>Muestra ambiental reproducida en el navegador</span></div></section>
       </div>
       <div className="lower-grid">
        <section id="sesion" className="panel session-panel"><CardHeader eyebrow="CONCENTRACIÓN" title="Tu próxima sesión" subtitle="Establece un tiempo para estudiar sin interrupciones." action={<span className="panel-icon"><Clock3 size={19}/></span>}/><div className="duration-row">{[15,25,45,60].map(v=><button key={v} onClick={()=>change({focusMinutes:v})} disabled={state.sessionActive||busy} className={'duration-chip '+(state.focusMinutes===v?'chosen':'')}>{v} min</button>)}</div><div className="timer-center"><div className="timer-ring"><div><strong>{formatSeconds(remaining)}</strong><small>{state.sessionActive?'Sesión en curso':'Lista para comenzar'}</small></div></div></div><button className={'session-button '+(state.sessionActive?'end':'')} onClick={()=>change({sessionActive:!state.sessionActive})} disabled={busy}>{state.sessionActive?<><Pause size={17} fill="currentColor"/> Finalizar sesión</>:<><Play size={17} fill="currentColor"/> Iniciar sesión de estudio</>}</button><div className="session-foot"><Check size={15}/> Iluminación sincronizada durante la sesión</div></section>
        <section id="dispositivo" className="panel device-panel"><CardHeader eyebrow="REALIDAD VIRTUAL" title="Conexión con Unreal" subtitle="Revisa la comunicación con tu experiencia inmersiva." action={<span className="panel-icon"><Headset size={19}/></span>}/><div className="device-banner"><div className="headset-disc"><Headset size={47} strokeWidth={1.45}/></div><div><div className="device-title">Unreal Engine · PC VR</div><Tag online={state.vrConnected}>{state.vrConnected?'Sala en ejecución':'Esperando Unreal'}</Tag></div></div><div className="setup-steps"><div><span className="step-count">01</span><p>Inicia el servidor local Node y este panel web.</p></div><div><span className="step-count">02</span><p>Abre la sala en Unreal Engine 5.7 con OpenXR habilitado.</p></div><div><span className="step-count">03</span><p>Conecta las gafas mediante Link/SteamVR y ejecuta VR Preview.</p></div></div><div className="device-disclaimer"><CircleHelp size={18}/><p>La conexión indica que Unreal consulta la API; <strong>no confirma</strong> que el visor esté conectado. Los ajustes de música se almacenan, pero el audio en el visor requiere una siguiente integración.</p></div></section>
       </div>
       <footer><span>StudySpace VR <b>·</b> Prototipo de investigación</span><span>React + Node.js + Unreal Engine 5.7 + OpenXR</span></footer>
     </div>
   </main>
 </div>;
}
export { RoomPreview };

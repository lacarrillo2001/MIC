import React, { useEffect, useState } from 'react';
import { Lightbulb, LogOut } from 'lucide-react';
import LocalMode from './LocalMode.jsx';
import Acceso from './components/Acceso.jsx';
import YouTubeDemo from './components/YouTubeDemo.jsx';
import YouTubeAutomatic, { AutomaticList } from './components/YouTubeAutomatic.jsx';
import * as bridgeApi from './api/puente.js';
import { setToken } from './api/client.js';
import './integrated.css';
import './study-layout.css';

export function Integrated({ user, logout }) {
  const [bridge, setBridge] = useState(null), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const [brightness, setBrightness] = useState(1.25), [preset, setPreset] = useState('neutro');
  useEffect(() => {
    let alive = true, running = false, initialized = false;
    async function refresh() {
      if(running) return; running = true;
      try { const data = await bridgeApi.state(); if(alive) {setBridge(data);setError('');if(!initialized){setBrightness(data.brightness);setPreset(data.lightingPreset);initialized=true;}} }
      catch(e) { if(alive) {setBridge(null);setError(e.message);} }
      finally { running = false; }
    }
    void refresh();const timer=setInterval(refresh,3500);return()=>{alive=false;clearInterval(timer);};
  }, []);
  async function applyLights() {setBusy(true);try{setBridge(await bridgeApi.settings({brightness,lightingPreset:preset}));setError('');}catch(e){setError(e.message);}finally{setBusy(false);}}
  return <div className="integrated-shell study-workspace"><header className="integrated-top"><a className="integrated-brand" href="#inicio">StudySpace<span>/ estudio</span></a><nav><a href="#audio-web">Mi sesión</a><a href="#ambiente">Ambiente</a></nav><button onClick={logout}><LogOut size={15} />Salir</button></header>
    <main id="inicio" className="integrated-main"><div className="workspace-heading"><div><p className="workspace-kicker">ESPACIO DE ESTUDIO</p><h1>Todo listo para empezar.</h1><p>Prepara tu música y ajusta la sala.</p></div><span className="workspace-account">{user.email}</span></div>
      <AutomaticList user={user} logout={logout} audioOnly embedded sidePanel={
      <section className="panel" id="ambiente"><div className="eyebrow"><Lightbulb size={14} /> AMBIENTE</div><h2>Iluminación de la sala</h2><p>Ajusta el color y la intensidad de la iluminación del entorno virtual.</p><fieldset disabled={busy || !bridge}>
        <label>Color de iluminación<select value={preset} onChange={e=>setPreset(e.target.value)}><option value="calido">Cálida</option><option value="neutro">Neutra</option><option value="frio">Fría</option></select></label>
        <label>Intensidad · {Math.round(brightness*100)}%<input type="range" style={{'--pct': `${((brightness-.2)/2.8)*100}%`}} min=".2" max="3" step=".05" value={brightness} onChange={e=>setBrightness(Number(e.target.value))} /></label>
        <button onClick={applyLights}>Aplicar ajustes en la sala</button></fieldset><p>{bridge?.vrConnected ? 'Sala virtual conectada.' : 'Esperando conexión de la sala virtual.'}</p>{error && <p role="alert">{error}</p>}</section>
      } /><details className="development-links"><summary>Pruebas de reproducción</summary><a href="/?prueba=youtube-auto" target="_blank" rel="noreferrer">Prueba directa de YouTube</a></details>
      <footer><span>StudySpace · Proyecto de investigación</span><span>Lectura comprensiva / Atención visual</span></footer>
    </main></div>;
}
export default function App() {
  const youtubeDemo = new URLSearchParams(window.location.search).get('prueba') === 'youtube';
  const youtubeAutomatic = new URLSearchParams(window.location.search).get('prueba') === 'youtube-auto';
  const [mode, setMode] = useState(null), [user, setUser] = useState(null), [error, setError] = useState('');
  async function load() { try { const config = await bridgeApi.configuration(); setMode(config.mode); setError(''); } catch (e) { setError(e.message); } }
  useEffect(() => { if (!youtubeDemo && !youtubeAutomatic) void load(); }, [youtubeDemo, youtubeAutomatic]);
  if (youtubeAutomatic) return <YouTubeAutomatic />;
  if (youtubeDemo) return <YouTubeDemo />;
  if (error) return <main className="access-wrap"><section className="panel"><h1>No se pudo conectar con el puente</h1><p role="alert">{error}</p><button onClick={load}>Reintentar</button></section></main>;
  if (!mode) return <main className="access-wrap"><p role="status">Comprobando conexión…</p></main>;
  if (mode === 'local') return <><div className="local-mode-note">Modo local · Demostración sin registro en Python.</div><LocalMode /></>;
  return user ? <Integrated user={user} logout={() => { setToken(''); setUser(null); }} /> : <main className="access-wrap"><div><Acceso onAccess={setUser} /><p className="youtube-shortcut"><a href="/?prueba=youtube-auto">YouTube con recomendaciones automáticas ↗</a></p><p className="youtube-shortcut"><a href="/?prueba=youtube">Prueba manual de YouTube sin cuenta ↗</a></p></div></main>;
}

import React, { useEffect, useState } from 'react';
import { artists } from '../api/recomendaciones.js';
import { getProfile, saveProfile } from '../api/usuarios.js';
import { request } from '../api/client.js';
export default function Preferencias({ locked }) {
  const [voice, setVoice] = useState(''), [search, setSearch] = useState('');
  const [genreOptions, setGenreOptions] = useState([]), [genreError, setGenreError] = useState('');
  const [profile, setProfile] = useState(null), [items, setItems] = useState([]), [page, setPage] = useState(1), [selected, setSelected] = useState([]), [genres, setGenres] = useState(''), [tempo, setTempo] = useState(''), [message, setMessage] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => { let current = true; getProfile().then(p => { if (!current) return; setProfile(p); setSelected(p.artistas_preferidos); setGenres(p.generos_preferidos.join(', ')); setTempo(p.tempo_preferido || ''); setVoice(p.preferencia_voz || ''); }).catch(e => current && setMessage(e.message)); return () => { current = false; }; }, []);
  useEffect(() => { let current = true; const timer = setTimeout(() => artists(page, search).then(data => current && setItems(data)).catch(e => current && setMessage(e.message)), 250); return () => { current = false; clearTimeout(timer); }; }, [page, search]);
  useEffect(() => {
    const controller = new AbortController(); let current = true;
    const timer = setTimeout(() => {
      const term = genres.split(',').at(-1).trim();
      request('/backend/catalogo/catalogo/generos?q=' + encodeURIComponent(term), { signal: controller.signal })
        .then(rows => { if (current) { setGenreOptions(rows); setGenreError(''); } })
        .catch(() => { if (current) setGenreError('No se pudieron cargar las sugerencias de géneros.'); });
    }, 250);
    return () => { current = false; clearTimeout(timer); controller.abort(); };
  }, [genres]);
  async function submit(e) {
    e.preventDefault(); setBusy(true);
    try { const names = [...new Set(genres.split(',').map(x => x.trim()).filter(Boolean))]; if (names.length > 3 || selected.length > 3) throw new Error('Selecciona hasta tres géneros y tres artistas.'); const p = await saveProfile({ version_esperada: profile.version, artistas_preferidos: selected, generos_preferidos: names, tempo_preferido: tempo || null, preferencia_voz: voice || null }); setProfile(p); setGenres(p.generos_preferidos.join(', ')); setMessage('Preferencias guardadas. Se utilizarán al preparar una lista nueva.'); }
    catch (e) { setMessage(e.message); if (e.status === 409) { const p = await getProfile().catch(() => null); if (p) setProfile(p); } } finally { setBusy(false); }
  }
  return <section className="panel" id="perfil"><div className="eyebrow">TU PERFIL MUSICAL</div><h2>Preferencias personales</h2><p>Selecciona artistas del catálogo. No confundimos tus gustos con una medición de tu estado emocional.</p><form onSubmit={submit}>
    <fieldset disabled={locked || busy || !profile}><legend>¿Qué artistas te gustaría escuchar mientras estudias? · {selected.length}/3</legend>
      <label>Buscar artistas (opcional)<input value={search} maxLength={100} onChange={e => { setSearch(e.target.value); setPage(1); }} /></label>
      {selected.length > 0 && <div className="button-row">{selected.map(id => <button type="button" key={id} onClick={() => setSelected(prev => prev.filter(x => x !== id))}>Quitar {items.find(a => a.id === id)?.name || id}</button>)}</div>}
      <div className="artist-list">{items.map(a => <label className="check-label" key={a._id}><input type="checkbox" checked={selected.includes(a.id)} disabled={!selected.includes(a.id) && selected.length >= 3} onChange={e => setSelected(prev => e.target.checked ? [...prev, a.id] : prev.filter(id => id !== a.id))} />{a.name}</label>)}{!items.length && <p>No hay artistas en esta página.</p>}</div>
      <div className="button-row"><button type="button" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Anterior</button><span>Página {page}</span><button type="button" disabled={items.length < 30} onClick={() => setPage(p => p + 1)}>Siguiente</button></div>
      <label>¿Qué géneros musicales prefieres para estudiar? (hasta tres, separados por comas)<input value={genres} maxLength={500} onChange={e => setGenres(e.target.value)} placeholder="ambiental, clásica…" /></label>
      <button type="button" onClick={() => setGenres('')}>No tengo preferencia de género</button>
      <p>Admitimos equivalencias como ambiental → ambient y clásica → classical. Elige una sugerencia para completar el último género; conserva los anteriores separados por comas.</p>
      <div className="button-row" aria-label="Sugerencias de géneros">{genreOptions.slice(0, 8).map(g => <button type="button" key={g.id} onClick={() => { const parts = genres.split(',').map(x => x.trim()); parts.pop(); setGenres([...parts.filter(Boolean), g.id].join(', ')); }}>{g.nombre}{g.nombre.toLowerCase() !== g.id ? ` · ${g.id}` : ''}</button>)}</div>
      {genreError && <p role="status">{genreError}</p>}
      <label>Para estudiar, ¿prefieres música instrumental o con voz?<select value={voice} onChange={e => setVoice(e.target.value)}><option value="">Sin preferencia</option><option value="instrumental">Instrumental</option><option value="con_voz">Con voz</option></select></label>
      <label>¿Qué ritmo musical prefieres mientras estudias?<select value={tempo} onChange={e => setTempo(e.target.value)}><option value="">Sin preferencia</option><option value="lento">Lento</option><option value="moderado">Moderado</option><option value="rapido">Rápido</option></select></label>
      <button className="primary-btn">Guardar preferencias</button></fieldset></form>{locked && <p>Perfil bloqueado mientras exista una sesión abierta.</p>}<p role="status">{message}</p>
  </section>;
}

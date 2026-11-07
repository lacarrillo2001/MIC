// Fixture en memoria. No abre MongoDB ni utiliza datos o credenciales del estudio.
export function fakeBackend(options = {}) {
  const uid = '111111111111111111111111', sid = '222222222222222222222222', rid = '333333333333333333333333', aid = '444444444444444444444444';
  let profile = { version: 1, artistas_preferidos: [], generos_preferidos: [], tempo_preferido: null, afinidad_aprendida: {} };
  let session = null, rec = null, linked = false, transitions = 0, events = [], toneAttempts = 0, surveyAttempts = 0;
  let youtubeEnabled = Boolean(options.youtubeConfigured), youtubeRec = null, youtubeRequests = [];
  let youtubeFeedback = null, youtubePlayed = false;
  let audioQueue = false, audioEvents = [];
  const audioIds = ['666666666666666666666661','666666666666666666666662','666666666666666666666663'];
  const response = (data, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } });
  const headers = o => new Headers(o.headers || {});
  const fixture = {
    uid, sid, rid, aid,
    stats: () => ({ transitions, events: [...events], toneAttempts, surveyAttempts, session, profile, youtubeRequests: [...youtubeRequests], audioEvents:[...audioEvents] }),
    enableAudioQueue: () => { audioQueue=true; },
    setYouTubeConfigured: value => { youtubeEnabled = Boolean(value); },
    async fetch(url, options = {}) {
      const u = new URL(url), path = u.pathname, method = options.method || 'GET', token = headers(options).get('Authorization'), body = options.body ? JSON.parse(options.body) : null;
      if (path === '/auth/login') return body.email === 'demo@example.test' && body.password === 'demo-password-123' ? response({ access_token: 'web-demo', expires_in: 7200 }) : response({ detail: 'Credenciales inválidas' }, 401);
      if (path === '/auth/registro') return response({ usuario_id: uid }, 201);
      if (!['Bearer web-demo', 'Bearer room-demo'].includes(token) && !path.endsWith('/canje')) return response({ detail: 'Token requerido' }, 401);
      if (token === 'Bearer room-demo' && !path.startsWith('/sesiones/')) return response({ detail: 'Token limitado a sala' }, 403);
      if (path === '/usuarios/me') return response({ _id: uid, email: 'demo@example.test', rol: 'estudiante' });
      if (path === '/catalogo/generos') {
        const choices = [{id:'ambient',nombre:'Ambiental'}, {id:'classical',nombre:'Clásica'}, {id:'white noise',nombre:'Ruido blanco'}];
        const term = (u.searchParams.get('q') || '').toLowerCase();
        return response(choices.filter(x => (x.id + ' ' + x.nombre.toLowerCase()).includes(term)));
      }
      if (path === '/youtube/configuracion') return response({ configurado: youtubeEnabled, solo_web_visible: true, cache_dias: 7 });
      if (path === '/youtube/feedback' && method === 'GET') return response(youtubeFeedback ? [youtubeFeedback] : []);
      if (path === '/youtube/voz' && method === 'GET') return response([]);
      if (path === `/youtube/recomendaciones/${rid}/voz` && method === 'GET') return response({tiene_voz:false,revision:0});
      if (path === `/youtube/recomendaciones/${rid}/reproduccion` && method === 'POST') {
        if (!youtubeRec?.canciones.some(x => x.track_id === body.track_id)) return response({ detail: 'Pista no recomendada' }, 422);
        youtubePlayed = true; audioEvents.push({tipo:'playing',track_id:body.track_id}); return response({ registrada: true });
      }
      if (path === `/youtube/recomendaciones/${rid}/feedback` && method === 'GET') return response({respuesta_actual:'neutral',revision_feedback:0});
      if (audioQueue && path === '/descargas' && method === 'POST') {
        const index = youtubeRec?.canciones.findIndex(x=>x.track_id===body.track_id) ?? -1;
        if(index<0) return response({detail:'Pista no incluida'},422);
        audioEvents.push({tipo:'preparar',track_id:body.track_id});
        return response({audio_id:audioIds[index],estado:index===0?'error':'disponible'},202);
      }
      if (audioQueue && path.startsWith('/descargas/')) {
        const id=path.split('/')[2], index=audioIds.indexOf(id);
        if(index<0) return response({detail:'No existe'},404);
        if(!path.endsWith('/contenido')) return response({audio_id:id,estado:index===0?'error':'disponible',error:index===0?'Fallo simulado para verificar salto automático':null});
        const samples=32000,buffer=Buffer.alloc(44+samples*2);
        buffer.write('RIFF',0);buffer.writeUInt32LE(buffer.length-8,4);buffer.write('WAVEfmt ',8);buffer.writeUInt32LE(16,16);
        buffer.writeUInt16LE(1,20);buffer.writeUInt16LE(1,22);buffer.writeUInt32LE(8000,24);buffer.writeUInt32LE(16000,28);
        buffer.writeUInt16LE(2,32);buffer.writeUInt16LE(16,34);buffer.write('data',36);buffer.writeUInt32LE(samples*2,40);
        // Audio sintético silencioso de cuatro segundos, no material del usuario.
        return new Response(buffer,{headers:{'Content-Type':'audio/wav'}});
      }
      if (path === `/youtube/recomendaciones/${rid}/feedback` && method === 'POST') {
        if (!youtubePlayed || !youtubeRec?.canciones.some(x => x.track_id === body.track_id)) return response({ detail: 'Reproduce la canción' }, 409);
        if (body.revision !== (youtubeFeedback?.revision || 0)) return response({ detail: 'Conflicto de revisión' }, 409);
        youtubeFeedback = { ...body, _id: '555555555555555555555555', recomendacion_id: rid, name: 'Video técnico de prueba (simulado)', revision: body.revision + 1 };
        return response(youtubeFeedback);
      }
      if (path === '/youtube/recomendaciones' && method === 'POST') {
        if (!youtubeEnabled && body.modo!=='audio') return response({ detail: 'Clave ausente en la fixture' }, 503);
        if (audioQueue && body.modo==='audio') {
          youtubeRec={_id:rid,tipo:'youtube_web',contexto_sesion:{actividad:body.actividad,duracion_minutos:body.duracion_minutos,energia_sesion:body.energia_sesion},canciones:[
            {track_id:'queue-error',name:'Pista no disponible (prueba)',artists:['Datos sintéticos']},
            {track_id:'queue-one',name:'Audio corto 1 (prueba)',artists:['Datos sintéticos']},
            {track_id:'queue-two',name:'Audio corto 2 (prueba)',artists:['Datos sintéticos']},
          ]}; return response(youtubeRec,201);
        }
        youtubeRec ||= { _id: rid, tipo: 'youtube_web', sesion_id: null, canciones: [
          { track_id: 'fixture-no-match', name: 'Primera pista sin coincidencia (simulada)', artists: ['Artista sintético'], duration_ms: 180000 },
          { track_id: 'fixture-video', name: 'Video técnico para prueba de interfaz (simulado)', artists: ['Datos sintéticos, no catálogo real'], duration_ms: 1344000 },
          { track_id: 'fixture-final', name: 'Última pista sin coincidencia (simulada)', artists: ['Artista sintético'], duration_ms: 180000 },
        ] };
        return response(youtubeRec, 201);
      }
      if (path === `/youtube/recomendaciones/${rid}/resolver` && method === 'POST') {
        if (!youtubeEnabled) return response({ detail: 'Clave ausente en la fixture' }, 503);
        if (!youtubeRec?.canciones.some(x => x.track_id === body.track_id)) return response({ detail: 'Pista no recomendada' }, 422);
        youtubeRequests.push(body.track_id);
        if (body.track_id !== 'fixture-video') return response({ estado: 'sin_coincidencia', track_id: body.track_id, motivo: 'Sin resultado, simulado para probar omisión automática' });
        return response({ estado: 'disponible', track_id: body.track_id, video_id: 'M7lc1UVf-VE', titulo_youtube: 'YouTube Developers Live: Embedded Web Player Customization', canal: 'Google for Developers', coincidencia: 'fixture_simulada', verificacion_acustica: false, respuesta_actual: youtubeFeedback?.respuesta || 'neutral', revision_feedback: youtubeFeedback?.revision || 0 });
      }
      if (path === '/perfiles/me') {
        if (method === 'PUT') {
          const aliases = { ambiental: 'ambient', 'clásica': 'classical', 'ruido blanco': 'white noise' };
          const genres = body.generos_preferidos.map(x => aliases[x.trim().toLowerCase()] || x.trim().toLowerCase());
          if (genres.some(x => !['ambient', 'classical', 'white noise'].includes(x))) return response({detail:'Género no reconocido. Selecciona una sugerencia.'}, 422);
          profile = { ...body, generos_preferidos: [...new Set(genres)], version: profile.version + 1, afinidad_aprendida: {} };
        }
        return response(profile);
      }
      if (path === '/catalogo/artistas') {
        const artists = [{_id:'artist-doc',id:'artist-demo',name:'Artista sintético',genres:['ambient']},
          {_id:'artist-doc-2',id:'artist-demo-2',name:'Piano de prueba',genres:['ambient']},
          {_id:'artist-doc-3',id:'artist-demo-3',name:'Ensamble demo',genres:['ambient']},
          {_id:'artist-doc-4',id:'artist-demo-4',name:'Cuarteto de prueba',genres:['ambient']}];
        const ids = u.searchParams.get('ids')?.split(','), q = (u.searchParams.get('q') || '').toLowerCase();
        return response(artists.filter(a=>(!ids || ids.includes(a.id)) && a.name.toLowerCase().includes(q)));
      }
      if (path === '/tonos/configuracion') return response({ version: 'fixture-tonos', aprobado: false, escala: { min: 1, max: 5 }, tonos: [] });
      if (path === '/evaluaciones-tonos') { toneAttempts++; return response({ detail: 'Protocolo pendiente de aprobación' }, 503); }
      if (path === '/encuestas/configuracion') return response({ version: 'fixture-survey', aprobado: false, preguntas: [] });
      if (path === '/sesiones' && method === 'POST') { session ||= { ...body, _id: sid, usuario_id: uid, estado: 'preparada', recomendacion_ids: [], eventos: [] }; return response(session, 201); }
      if (path === '/recomendaciones' && method === 'POST') {
        rec ||= { _id: rid, sesion_id: sid, canciones: [{ track_id: 'track-demo', audio_id: aid, name: 'Audio sintético de prueba', artists: ['Artista sintético'], puntaje_compatibilidad: 100, motivos: ['Fixture para probar integración, sin datos del estudio'] }] };
        if (!session.recomendacion_ids.includes(rid)) session.recomendacion_ids.push(rid); return response(rec, 201);
      }
      if (path === `/recomendaciones/${rid}`) return response(rec);
      if (path === `/sesiones/${sid}`) return response(session);
      if (path === `/sesiones/${sid}/vinculacion`) { if (linked) return response({ detail: 'Ya canjeado' }, 409); return response({ codigo: 'c'.repeat(43) }); }
      if (path === `/sesiones/${sid}/canje`) { if (linked || body.codigo !== 'c'.repeat(43)) return response({ detail: 'Código inválido' }, 403); linked = true; return response({ access_token: 'room-demo', expires_in: 1800 }); }
      if (path === `/sesiones/${sid}/estado`) {
        if (token !== 'Bearer room-demo' && body.estado !== 'interrumpida') return response({ detail: 'Solo sala' }, 403);
        if (session.estado !== body.estado) { transitions++; session.estado = body.estado; if (body.estado === 'activa') session.inicio ||= new Date().toISOString(); if (['finalizada', 'interrumpida'].includes(body.estado)) session.fin = new Date().toISOString(); }
        return response({ estado: session.estado });
      }
      if (path === `/sesiones/${sid}/eventos`) { if (!events.find(x => x.evento_id === body.evento_id)) events.push(body); return response({ registrado: true }); }
      if (path === `/sesiones/${sid}/encuesta`) { surveyAttempts++; return response({ detail: 'Cuestionario no aprobado' }, 503); }
      if (path === '/feedback') return response({ _id: 'feedback-demo', estado_ajuste: 'sin_cambio' }, 201);
      if (path === `/audios/${aid}/contenido`) {
        const buffer = Buffer.alloc(16044); buffer.write('RIFF', 0); buffer.writeUInt32LE(16036, 4); buffer.write('WAVEfmt ', 8); buffer.writeUInt32LE(16, 16); buffer.writeUInt16LE(1, 20); buffer.writeUInt16LE(1, 22); buffer.writeUInt32LE(8000, 24); buffer.writeUInt32LE(16000, 28); buffer.writeUInt16LE(2, 32); buffer.writeUInt16LE(16, 34); buffer.write('data', 36); buffer.writeUInt32LE(16000, 40);
        return new Response(buffer, { status: 200, headers: { 'Content-Type': 'audio/wav' } });
      }
      return response({ detail: 'Ruta fixture desconocida' }, 404);
    },
  };
  return fixture;
}

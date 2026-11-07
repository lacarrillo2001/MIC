// No busca, descarga ni extrae audio: solo valida un ID para el reproductor oficial.
export function videoIdFromInput(input) {
  const value = String(input || '').trim();
  if (/^[A-Za-z0-9_-]{11}$/.test(value)) return value;
  let url;
  try { url = new URL(value); } catch { throw new Error('Pega un enlace HTTPS de un video de YouTube o su ID de 11 caracteres.'); }
  const hosts = new Set(['youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com', 'youtu.be', 'www.youtu.be', 'www.youtube-nocookie.com']);
  if (url.protocol !== 'https:' || !hosts.has(url.hostname) || url.username || url.password || url.port) throw new Error('Solo se permiten enlaces HTTPS oficiales de YouTube.');
  const parts = url.pathname.split('/').filter(Boolean);
  let id;
  if (url.hostname.endsWith('youtu.be') && parts.length === 1) id = parts[0];
  else if (url.pathname === '/watch' && url.searchParams.getAll('v').length === 1) id = url.searchParams.get('v');
  else if (parts.length === 2 && ['embed', 'shorts', 'live'].includes(parts[0])) id = parts[1];
  if (!/^[A-Za-z0-9_-]{11}$/.test(id || '')) throw new Error('El enlace debe identificar un video, no solo un canal o una lista.');
  return id;
}

export function playerErrorMessage(code) {
  const errors = {
    2: 'El identificador del video no es válido.',
    5: 'El navegador no pudo reproducir este video HTML5.',
    100: 'El video no existe, es privado o fue retirado.',
    101: 'El propietario no permite reproducir este video en otras páginas.',
    150: 'El propietario no permite reproducir este video en otras páginas.',
    153: 'YouTube no pudo verificar el origen de la página. Prueba esta URL local en Chrome o Edge; no se omitirá esa comprobación.',
  };
  return errors[code] || `YouTube informó un error (${code}). Prueba otro video que permita inserción.`;
}

let loading;
export function loadYouTubeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (loading) return loading;
  loading = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    const previous = window.onYouTubeIframeAPIReady;
    let timer;
    const fail = () => { clearTimeout(timer); script.remove(); loading = null; if (window.onYouTubeIframeAPIReady === ready) window.onYouTubeIframeAPIReady = previous; reject(new Error('No se pudo cargar el reproductor de YouTube. Comprueba Internet, las extensiones y la configuración del navegador.')); };
    const ready = () => { clearTimeout(timer); if (typeof previous === 'function') { try { previous(); } catch {} } resolve(window.YT); };
    window.onYouTubeIframeAPIReady = ready;
    script.src = 'https://www.youtube.com/iframe_api';
    script.async = true;
    script.onerror = fail;
    timer = setTimeout(fail, 20000);
    document.head.appendChild(script);
  });
  return loading;
}

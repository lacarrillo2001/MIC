import { request } from './client.js';
const base = '/backend/catalogo';
export const artists = (pagina = 1, q = '', ids = []) => request(base + `/catalogo/artistas?pagina=${pagina}&limite=30&q=${encodeURIComponent(q)}${ids.length ? '&ids=' + encodeURIComponent(ids.join(',')) : ''}`);
export const recommend = (body) => request(base + '/recomendaciones', { method: 'POST', body });
export const getRecommendation = (id) => request(base + `/recomendaciones/${id}`);
export const feedback = (body) => request(base + '/feedback', { method: 'POST', body });

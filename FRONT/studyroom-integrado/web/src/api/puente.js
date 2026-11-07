import { request } from './client.js';
export const configuration = () => request('/api/config', { authenticated: false });
export const state = () => request('/api/state');
export const settings = (body) => request('/api/state', { method: 'PATCH', body });
export const bind = (body) => request('/api/session/link', { method: 'POST', body });
export const command = (body) => request('/api/session/command', { method: 'POST', body });
export const release = () => request('/api/session/release', { method: 'POST' });

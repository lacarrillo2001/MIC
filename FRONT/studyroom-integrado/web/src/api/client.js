let accessToken = ''; // Solo memoria: no persistir contraseñas ni tokens en almacenamiento web.
export function setToken(value) { accessToken = value || ''; }
export function getToken() { return accessToken; }
export class RequestError extends Error { constructor(status, message) { super(message); this.status = status; } }
export async function request(path, { method = 'GET', body, blob = false, signal, authenticated = true } = {}) {
  let response;
  try {
    response = await fetch(path, { method, cache: 'no-store', signal: signal || AbortSignal.timeout(blob ? 60000 : 15000),
      headers: { ...(authenticated && accessToken ? { Authorization: `Bearer ${accessToken}` } : {}), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
      body: body === undefined ? undefined : JSON.stringify(body) });
  } catch { throw new RequestError(503, 'No se pudo conectar. Comprueba el puente y el backend; la operación puede haber sido recibida, reintenta sin cambiar sus datos.'); }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new RequestError(response.status, typeof data.detail === 'string' ? data.detail : data.error || `Solicitud rechazada (${response.status})`);
  }
  return blob ? response.blob() : response.json();
}
export const newId = () => crypto.randomUUID();

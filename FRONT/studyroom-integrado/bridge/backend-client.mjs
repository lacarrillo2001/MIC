export class ApiError extends Error {
  constructor(status, message) { super(message); this.status = status; }
}
export class BackendClient {
  constructor(bases, fetcher = fetch) { this.bases = bases; this.fetcher = fetcher; }
  async raw(service, path, { method = 'GET', token, body, range, signal } = {}) {
    if (!this.bases[service] || !path.startsWith('/') || path.startsWith('//')) throw new ApiError(400, 'Destino inválido');
    try {
      return await this.fetcher(this.bases[service] + path, { method, redirect: 'error',
        headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(range ? { Range: range } : {}) },
        body: body === undefined ? undefined : JSON.stringify(body), signal: signal || AbortSignal.timeout(12000) });
    } catch { throw new ApiError(503, 'El backend no responde. No se activará el modo local automáticamente.'); }
  }
  async json(service, path, options) {
    const response = await this.raw(service, path, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new ApiError(response.status, typeof data.detail === 'string' ? data.detail : 'El backend rechazó los datos enviados');
    return data;
  }
}

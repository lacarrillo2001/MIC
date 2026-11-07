import { ApiError } from './backend-client.mjs';

const terminal = new Set(['finalizada', 'interrumpida']);
export class SessionLink {
  #token = null;
  #link = null;
  #pending = null;
  #history = new Map();
  #working = false;
  constructor(client) { this.client = client; }
  get linked() { return Boolean(this.#link); }
  async owner(webToken) {
    const user = await this.client.json('usuarios', '/usuarios/me', { token: webToken });
    if (this.#link && this.#link.usuario_id !== user._id) throw new ApiError(403, 'El puente está ocupado por otro participante');
    return user;
  }
  async bind({ sesion_id, codigo }, webToken) {
    if (this.#working) throw new ApiError(409, 'Operación en curso');
    this.#working = true;
    try {
      await this.owner(webToken);
      if (this.#link) {
        if (this.#link._id === sesion_id) return this.snapshot();
        throw new ApiError(409, 'Liberar la sesión anterior antes de vincular otra');
      }
      const session = await this.client.json('sesiones', `/sesiones/${sesion_id}`, { token: webToken });
      if (session.estado !== 'preparada' || !session.recomendacion_ids?.length) throw new ApiError(409, 'Preparar la sesión y su recomendación antes de vincular');
      if (![15, 25].includes(Number(session.actividad?.duracion_minutos))) throw new ApiError(409, 'El piloto admite 15 o 25 minutos por el plazo del token de sala');
      const brightness = Number(session.actividad?.brillo_multiplicador);
      if (!Number.isFinite(brightness) || brightness < .2 || brightness > 3 || !['calido', 'neutro', 'frio'].includes(session.actividad?.preset_iluminacion)) throw new ApiError(409, 'Falta la configuración de iluminación de la actividad');
      const result = await this.client.json('sesiones', `/sesiones/${sesion_id}/canje`, { method: 'POST', body: { codigo } });
      this.#token = result.access_token;
      this.#link = session;
      this.expiresAt = Date.now() + result.expires_in * 1000;
      this.#pending = null;
      this.#history.clear();
      return this.snapshot();
    } finally { this.#working = false; }
  }
  snapshot() {
    return { sesion_id: this.#link?._id || null, estado: this.#link?.estado || null,
      sessionStartedAt: this.#link?.inicio || null, focusMinutes: Number(this.#link?.actividad?.duracion_minutos) || 25,
      expiresAt: this.#link ? new Date(this.expiresAt).toISOString() : null,
      sceneSettings: this.#link ? { brightness: Number(this.#link.actividad.brillo_multiplicador), lightingPreset: this.#link.actividad.preset_iluminacion } : null,
      pendiente: this.#pending ? { ...this.#pending } : null };
  }
  async refresh(webToken) {
    if (webToken) await this.owner(webToken);
    if (!this.#link) return this.snapshot();
    if (!webToken && Date.now() >= this.expiresAt) throw new ApiError(401, 'Token de sala vencido; interrumpir desde la web y crear otra sesión');
    this.#link = await this.client.json('sesiones', `/sesiones/${this.#link._id}`, { token: webToken || this.#token });
    if (terminal.has(this.#link.estado)) this.#pending = null;
    return this.snapshot();
  }
  async command(body, webToken) {
    await this.refresh(webToken);
    if (!this.#link) throw new ApiError(409, 'No hay sala vinculada');
    if (Date.now() >= this.expiresAt) throw new ApiError(401, 'Token de sala vencido');
    if (this.#pending) {
      if (this.#pending.id === body.id && this.#pending.estado === body.estado) return this.snapshot();
      throw new ApiError(409, 'Unreal debe confirmar el comando pendiente');
    }
    if (this.#history.has(body.id)) {
      if (this.#history.get(body.id).estado !== body.estado) throw new ApiError(409, 'Identificador reutilizado');
      return this.snapshot();
    }
    const graph = { preparada: ['activa'], activa: ['pausada', 'finalizada', 'interrumpida'], pausada: ['activa', 'finalizada', 'interrumpida'] };
    if (!graph[this.#link.estado]?.includes(body.estado)) throw new ApiError(409, 'Transición no permitida');
    this.#pending = { id: body.id, estado: body.estado, sesion_id: this.#link._id };
    return this.snapshot();
  }
  async confirm(body) {
    if (this.#working) throw new ApiError(409, 'Operación en curso; reenviar la confirmación');
    this.#working = true;
    try {
      if (!this.#link || body.sesion_id !== this.#link._id) throw new ApiError(403, 'Sesión distinta');
      const previous = this.#history.get(body.id);
      if (previous) {
        if (previous.estado !== body.estado) throw new ApiError(409, 'Comando reutilizado con otros datos');
        return this.snapshot();
      }
      const unsolicitedStop = body.estado === 'interrumpida' && ['activa', 'pausada'].includes(this.#link.estado);
      if (!unsolicitedStop && (!this.#pending || this.#pending.id !== body.id || this.#pending.estado !== body.estado)) throw new ApiError(409, 'Confirmación sin comando pendiente');
      await this.client.json('sesiones', `/sesiones/${this.#link._id}/estado`, { method: 'POST', token: this.#token, body: { estado: body.estado } });
      this.#link.estado = body.estado;
      // Leer el estado oficial, incluidos sus tiempos. Si falla, el próximo ACK es seguro.
      await this.refresh();
      this.#history.set(body.id, { ...body });
      while (this.#history.size > 30) this.#history.delete(this.#history.keys().next().value);
      this.#pending = null;
      return this.snapshot();
    } finally { this.#working = false; }
  }
  async release(webToken) {
    await this.refresh(webToken);
    if (this.#link && !terminal.has(this.#link.estado)) throw new ApiError(409, 'Cerrar o interrumpir la sesión antes de liberar');
    this.#token = null; this.#link = null; this.#pending = null; this.#history.clear();
    return this.snapshot();
  }
}

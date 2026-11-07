import React, { useState } from 'react';
import { login, register, me } from '../api/usuarios.js';
import { setToken } from '../api/client.js';
export default function Acceso({ onAccess }) {
  const [signup, setSignup] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState('');
  async function submit(e) {
    e.preventDefault(); setBusy(true); setError('');
    const data = new FormData(e.currentTarget);
    try {
      if (signup) await register({ email: data.get('email'), password: data.get('password'), mayor_edad_confirmado: data.get('adult') === 'on', consentimiento_aceptado: data.get('consent') === 'on', consentimiento_version: 'consentimiento-v1' });
      const auth = await login({ email: data.get('email'), password: data.get('password') });
      setToken(auth.access_token);
      onAccess(await me());
    } catch (e) { setToken(''); setError(e.message); } finally { setBusy(false); }
  }
  return <section className="panel access-panel"><div className="eyebrow">STUDYSPACE · MODO INTEGRADO</div><h1>{signup ? 'Crear cuenta' : 'Acceder a tu espacio'}</h1><p>Tu perfil, tu música y tu sala, vinculados a una misma sesión.</p>
    <form onSubmit={submit}><label>Correo<input name="email" type="email" required maxLength={254} autoComplete="email" /></label><label>Contraseña<input name="password" type="password" minLength={signup ? 12 : 1} maxLength={128} required autoComplete={signup ? 'new-password' : 'current-password'} /></label>
      {signup && <><div className="info-note">Registro técnico del prototipo. Antes de participar, el investigador debe proporcionarte el texto aprobado de consentimiento-v1; este aviso no lo sustituye.</div><label className="check-label"><input name="adult" type="checkbox" required />Confirmo que tengo 18 años o más.</label><label className="check-label"><input name="consent" type="checkbox" required />He recibido, leído y aceptado el consentimiento-v1 proporcionado por el investigador.</label></>}
      {error && <p role="alert" className="form-error">{error}</p>}<button className="primary-btn" disabled={busy}>{busy ? 'Conectando…' : signup ? 'Registrarme y acceder' : 'Iniciar sesión'}</button>
    </form><button className="text-button" disabled={busy} onClick={() => { setSignup(!signup); setError(''); }}>{signup ? 'Ya tengo cuenta' : 'Crear una cuenta de estudiante'}</button>
  </section>;
}

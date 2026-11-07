"""Genera secretos locales sin imprimirlos y sin sobrescribir un .env existente."""
from pathlib import Path
import secrets

root = Path(__file__).resolve().parents[1]
keys = ['MONGO_ROOT_PASSWORD', 'USUARIOS_DB_PASSWORD', 'RECOMENDACION_DB_PASSWORD',
        'SESIONES_DB_PASSWORD', 'JWT_SECRET', 'USUARIOS_SERVICE_KEY',
        'RECOMENDACION_SERVICE_KEY', 'SESIONES_SERVICE_KEY']
target = root / '.env'
if target.exists():
    raise SystemExit('.env ya existe; no se ha modificado.')
with target.open('x', encoding='utf-8') as stream:
    stream.write('\n'.join(f'{key}={secrets.token_hex(32)}' for key in keys))
    stream.write('\nCORS_ORIGINS=http://localhost:3000,http://localhost:5173\n')
print('Archivo .env creado. No publicarlo ni compartirlo.')

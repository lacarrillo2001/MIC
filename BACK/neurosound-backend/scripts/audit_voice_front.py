"""Solo lectura: evidencia sin credenciales ni identificadores personales."""
import json
import os
from pymongo import MongoClient

client = MongoClient(host=os.environ['MONGO_HOST'], username=os.environ['MONGO_USER'],
                     password=os.environ['MONGO_PASSWORD'], authSource=os.environ['MONGO_DATABASE'])
db = client[os.environ['MONGO_DATABASE']]
lists = list(db.recomendaciones.find({'tipo': 'youtube_web', 'reglas_version': 'encuesta-web-v4'}).sort('creado_en', -1).limit(3))
result = []
for rec in lists:
    uid = rec['usuario_id']
    reports = list(db.feedback.find({'usuario_id': uid, 'tipo': 'voz_web'}))
    result.append({'creada_en': rec['creado_en'].isoformat(), 'preferencia': rec['perfil_utilizado'].get('preferencia_voz'),
        'preseleccion': rec.get('preseleccion_voz'),
        'canciones': [{'track_id': s['track_id'], 'titulo': s['name'],
                       'instrumentalness': s['atributos_utilizados'].get('instrumentalness'),
                       'clasificacion': s.get('clasificacion_voz'), 'reproducida': s['track_id'] in rec.get('reproducidas', [])}
                      for s in rec['canciones']],
        'reportes': [{'track_id': r['track_id'], 'tiene_voz': r['tiene_voz'], 'revision': r['revision']} for r in reports],
        'valoraciones_musicales': db.feedback.count_documents({'usuario_id': uid, 'tipo': 'youtube_web'})})
print(json.dumps(result, ensure_ascii=False, indent=2))

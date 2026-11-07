"""Comprobación manual de descarga; ejecutar explícitamente dentro del contenedor."""
import json
import os
from pymongo import MongoClient
from sesiones.downloads import cache_key, prepare_audio, public

db = MongoClient(host=os.environ['MONGO_HOST'],username=os.environ['MONGO_USER'],password=os.environ['MONGO_PASSWORD'],
                 authSource=os.environ['MONGO_DATABASE'])[os.environ['MONGO_DATABASE']]
song = {'track_id':'0VdfL7wQBI5eLjFvM7Ylam','name':'Chufuku','artists':['Emus DJ','Tiburon Valdez'],'duration_ms':194456}
key = cache_key(song)
item = db.audios.find_one({'cache_key':key})
if not item or item.get('estado_descarga') != 'disponible':
    if item:
        aid = item['_id']
    else:
        aid = db.audios.insert_one({'cache_key':key,'track_id':song['track_id'],'tipo':'cancion',
            'fuente':'youtube_descarga','fuente_autorizada':False,'correspondencia_verificada':False,'estado_descarga':'descargando'}).inserted_id
    prepare_audio(db,aid,song)
    item = db.audios.find_one({'_id':aid})
print(json.dumps({**public(item),'tipo_error':item.get('tipo_error'),'video_id':item.get('video_id')},ensure_ascii=False))

import json
from pathlib import Path
from types import SimpleNamespace

from bson import ObjectId
from sesiones.match_audio import choose_video
from sesiones import downloads


SONG = {'track_id':'track-download','name':'Quiet Song','artists':['Test Artist'],'duration_ms':180000}
VIDEO = {'id':'abc12345678','title':'Test Artist - Quiet Song','duration':180,'channel':'Test Artist'}


def test_match_rejects_versions_artist_duration_and_invalid_ids():
    assert choose_video(SONG, [VIDEO]) == VIDEO
    for change in [{'title':'Test Artist - Quiet Song BASS BOOSTED'}, {'title':'Another - Quiet Song','channel':'Another'},
                   {'duration':500}, {'id':'../../bad'}, {'is_live':True}, {'age_limit':18}]:
        assert choose_video(SONG, [{**VIDEO, **change}]) is None


def test_worker_actual_conversion_command_and_failure_state(system, monkeypatch, tmp_path):
    _, db, _ = system
    monkeypatch.setenv('MEDIA_ROOT',str(tmp_path))
    aid = db.audios.insert_one({'estado_descarga':'descargando'}).inserted_id
    calls=[]
    def command(args, timeout):
        calls.append(args)
        if '--dump-single-json' in args:
            return SimpleNamespace(stdout=json.dumps({'entries':[VIDEO]}))
        if args[0]=='ffprobe':
            return SimpleNamespace(stdout=json.dumps({'streams':[{'codec_name':'mp3','codec_type':'audio'}],'format':{'duration':'180'}}))
        (tmp_path/'descargas'/str(aid)/'audio.mp3').write_bytes(b'test fixture')
        return SimpleNamespace(stdout='')
    monkeypatch.setattr(downloads,'run_command',command)
    downloads.prepare_audio(db,aid,SONG)
    audio=db.audios.find_one({'_id':aid})
    assert audio['estado_descarga']=='disponible' and audio['formato']=='audio/mpeg'
    assert any('--audio-format' in args and 'mp3' in args for args in calls)
    assert not any('--cookies' in args for args in calls)
    def fail(*args,**kwargs):
        raise RuntimeError('failure')
    monkeypatch.setattr(downloads,'run_command',fail)
    downloads.prepare_audio(db,aid,SONG)
    assert db.audios.find_one({'_id':aid})['estado_descarga']=='error'
    assert not (tmp_path/'descargas'/str(aid)/'audio.mp3').exists()


def test_download_requires_owned_web_recommendation_and_cache_reused(system,student,monkeypatch,tmp_path):
    clients,db,_=system
    headers,uid=student
    monkeypatch.setenv('MEDIA_ROOT',str(tmp_path))
    rec_id=db.recomendaciones.insert_one({'usuario_id':uid,'tipo':'youtube_web','canciones':[SONG]}).inserted_id
    key=downloads.cache_key(SONG)
    path=tmp_path/'fixture.mp3'; path.write_bytes(b'test fixture')
    aid=db.audios.insert_one({'track_id':SONG['track_id'],'cache_key':key,'estado_descarga':'disponible','ubicacion':'fixture.mp3'}).inserted_id
    api=clients['sesiones']
    body={'recomendacion_id':str(rec_id),'track_id':SONG['track_id']}
    result=api.post('/descargas',headers=headers,json=body)
    assert result.status_code==202 and result.json()['audio_id']==str(aid)
    assert db.audios.count_documents({})==1
    assert api.post('/descargas',headers=headers,json={**body,'track_id':'unlisted'}).status_code==422
    assert api.get(f'/descargas/{aid}?recomendacion_id={rec_id}',headers=headers).json()['estado']=='disponible'
    assert api.get(f'/descargas/{aid}/contenido?recomendacion_id={rec_id}',headers=headers).content==b'test fixture'
    partial=api.get(f'/descargas/{aid}/contenido?recomendacion_id={rec_id}',headers={**headers,'Range':'bytes=0-3'})
    assert partial.status_code==206 and partial.content==b'test'
    db.recomendaciones.update_one({'_id':rec_id},{'$set':{'usuario_id':str(ObjectId())}})
    assert api.post('/descargas',headers=headers,json=body).status_code==403


def test_audio_list_without_youtube_api_key(system,student,monkeypatch):
    clients,db,_=system
    headers,uid=student
    monkeypatch.delenv('YOUTUBE_API_KEY',raising=False)
    db.songsV2.insert_one({'id':SONG['track_id'],**SONG,'id_artists':[]})
    response=clients['recomendacion'].post('/youtube/recomendaciones',headers=headers,json={'solicitud_id':'audio-list-no-key','modo':'audio'})
    assert response.status_code==201,response.text
    rec=response.json()
    assert rec['modo_reproduccion']=='audio'
    opinion=clients['recomendacion'].get(f"/youtube/recomendaciones/{rec['_id']}/feedback?track_id={SONG['track_id']}",headers=headers)
    assert opinion.json()=={'respuesta_actual':'neutral','revision_feedback':0}

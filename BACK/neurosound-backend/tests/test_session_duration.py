from datetime import datetime, timedelta, timezone
import recomendacion.youtube_api as youtube


def test_duration_limits_and_deadline(system, student, monkeypatch):
    clients, db, _ = system
    headers, _ = student
    api = clients['recomendacion']
    db.songsV2.insert_one({'id':'clock-song','name':'Clock','artists':['Artist'],'duration_ms':180000})
    for duration in (2, 11, 25):
        body = {'solicitud_id':f'duration-{duration}', 'modo':'audio', 'duracion_minutos':duration}
        assert api.post('/youtube/recomendaciones', headers=headers, json=body).status_code == 422
        assert clients['sesiones'].post('/sesiones', headers=headers, json={'solicitud_id':f'vr-duration-{duration}', 'actividad':{'duracion_minutos':str(duration)}}).status_code == 422
    moment = datetime(2026, 11, 7, tzinfo=timezone.utc)
    monkeypatch.setattr(youtube, 'now', lambda: moment)
    rec = api.post('/youtube/recomendaciones', headers=headers, json={'solicitud_id':'duration-valid', 'modo':'audio', 'duracion_minutos':3})
    assert rec.status_code == 201, rec.text
    root = '/youtube/recomendaciones/' + rec.json()['_id'] + '/reproduccion'
    first = api.post(root, headers=headers, json={'track_id':'clock-song'})
    assert first.status_code == 200 and first.json()['duracion_minutos'] == 3
    moment += timedelta(seconds=100)
    assert api.post(root, headers=headers, json={'track_id':'clock-song'}).json()['inicio_web'] == first.json()['inicio_web']
    moment += timedelta(seconds=81)
    assert api.post(root, headers=headers, json={'track_id':'clock-song'}).status_code == 409
    assert clients['sesiones'].post('/sesiones', headers=headers, json={'solicitud_id':'vr-duration-valid', 'actividad':{'duracion_minutos':'10'}}).status_code == 201

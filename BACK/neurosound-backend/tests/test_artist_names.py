def test_saved_artist_names_resolved_by_ids(system, student):
    clients, db, _ = system
    headers, _ = student
    db.artists.insert_many([{'id':'first','name':'First Artist'}, {'id':'saved','name':'Saved Artist'}])
    api = clients['recomendacion']
    result = api.get('/catalogo/artistas?ids=saved', headers=headers)
    assert result.status_code == 200
    assert [a['id'] for a in result.json()] == ['saved']
    assert api.get('/catalogo/artistas?ids=saved&q=First', headers=headers).json() == []
    assert api.get('/catalogo/artistas?ids=first,,saved', headers=headers).status_code == 422

// Migración aditiva para una base ya inicializada. No cambia datos ni otras cuentas.
if (!db.getSiblingDB('admin').auth('root', process.env.MONGO_INITDB_ROOT_PASSWORD)) {
  throw new Error('No se pudo autenticar la migracion local');
}
const catalogueDb = db.getSiblingDB('neurosound');
catalogueDb.grantPrivilegesToRole('recomendacion_collections', [{
  resource: {db: 'neurosound', collection: 'youtube_vinculos'},
  actions: ['find', 'insert', 'update', 'createCollection', 'createIndex', 'listIndexes']
}]);
print('Permisos de cache YouTube actualizados; catalogo original intacto.');

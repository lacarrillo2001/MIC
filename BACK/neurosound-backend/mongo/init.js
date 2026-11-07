// Solo usuarios y permisos. Las colecciones las crea cada API en CADA arranque.
const database = db.getSiblingDB('neurosound');
const collections = {
  usuarios: ['usuarios', 'perfiles', 'evaluaciones_tonos'],
  recomendacion: ['songsV2', 'artists', 'recomendaciones', 'feedback', 'youtube_vinculos'],
  sesiones: ['audios', 'sesiones', 'encuestas']
};
for (const [service, names] of Object.entries(collections)) {
  const role = `${service}_collections`;
  database.createRole({role, privileges: names.map(collection => ({
    resource: {db: 'neurosound', collection},
    actions: ['find', 'insert', 'update', 'createCollection', 'createIndex', 'listIndexes']
  })), roles: []});
  database.createUser({user: service, pwd: process.env[`${service.toUpperCase()}_DB_PASSWORD`],
    roles: [{role, db: 'neurosound'}]});
}

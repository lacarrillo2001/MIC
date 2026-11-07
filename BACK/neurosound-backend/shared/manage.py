"""Administración local explícita; no se ejecuta automáticamente al arrancar."""
import argparse
import getpass
import os
from pathlib import Path

from bson import json_util
from pymongo import MongoClient

from shared.runtime import now, password_hash


def connect():
    return MongoClient(host=os.environ["MONGO_HOST"], username=os.environ["MONGO_USER"],
        password=os.environ["MONGO_PASSWORD"], authSource=os.environ.get("MONGO_DATABASE", "neurosound"),
        serverSelectionTimeoutMS=5000)[os.environ.get("MONGO_DATABASE", "neurosound")]


def import_catalogue(db, filename, collection):
    root = Path("/imports").resolve()
    path = Path(filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise SystemExit("Usar un archivo del directorio /imports montado en el contenedor")
    from shared.catalogue import load_file
    result = load_file(db, path, collection)
    if result["conflictos_conservados"] or result["colisiones_concurrentes"]:
        raise SystemExit(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    researcher = commands.add_parser("crear-investigador")
    researcher.add_argument("email")
    catalogue = commands.add_parser("importar")
    catalogue.add_argument("archivo")
    catalogue.add_argument("--coleccion", choices=["songsV2", "artists"], required=True)
    args = parser.parse_args()
    db = connect()
    if args.command == "importar":
        if os.environ.get("MONGO_USER") != "recomendacion":
            raise SystemExit("Ejecutar desde recomendacion")
        import_catalogue(db, args.archivo, args.coleccion)
    else:
        if os.environ.get("MONGO_USER") != "usuarios":
            raise SystemExit("Ejecutar desde usuarios")
        email = args.email.strip().lower()
        if "@" not in email or db.usuarios.find_one({"email": email}):
            raise SystemExit("Correo inválido o ya registrado. No se modifica su rol automáticamente")
        password = getpass.getpass("Contraseña (mínimo 12 caracteres): ")
        if len(password) < 12 or len(password) > 128 or password != getpass.getpass("Repetir contraseña: "):
            raise SystemExit("Contraseña inválida o no coincide")
        user = {"email": email, "password_hash": password_hash(password), "rol": "investigador",
                "mayor_edad_confirmado": True, "estado": "activo", "creado_en": now(),
                "consentimiento": {"aceptado": True, "version": "consentimiento-v1", "aceptado_en": now()}}
        confirmation = input("Confirmar mayoría de edad y aceptación del consentimiento-v1 del investigador (SI): ")
        if confirmation != "SI":
            raise SystemExit("Cancelado; no se guardaron datos")
        uid = db.usuarios.insert_one(user).inserted_id
        db.perfiles.insert_one({"usuario_id": uid, "artistas_preferidos": [], "generos_preferidos": [],
            "tempo_preferido": None, "afinidad_aprendida": {}, "version": 1, "feedback_aplicados": [], "actualizado_en": now()})
        print("Investigador creado. Iniciar sesión mediante /auth/login.")


if __name__ == "__main__":
    main()

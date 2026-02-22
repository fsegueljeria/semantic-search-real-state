#!/usr/bin/env python3
"""
Limpiar la base de datos vectorial (Qdrant)
===========================================

Elimina la colección de propiedades para permitir una nueva carga masiva desde cero.
Tras ejecutar este script, puedes correr el ETL para volver a cargar los datos.

Uso:
  python scripts/clean_vector_db.py              # pide confirmación
  python scripts/clean_vector_db.py --force      # sin confirmación (scripts/CI)
  python scripts/clean_vector_db.py --collection otra_coleccion
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.db.client import qdrant


def main():
    parser = argparse.ArgumentParser(
        description="Elimina la colección vectorial para preparar una nueva carga masiva.",
        epilog="Luego ejecuta: python -m src.etl.main --recreate (o -y) para cargar de nuevo.",
    )
    parser.add_argument(
        "--collection",
        "-c",
        type=str,
        default=settings.qdrant_collection_name,
        help=f"Nombre de la colección a eliminar (default: {settings.qdrant_collection_name})",
    )
    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="No pedir confirmación (útil para scripts o CI).",
    )
    args = parser.parse_args()

    collection_name = args.collection

    print(f"\n🗄️  Base vectorial: {settings.qdrant_host}:{settings.qdrant_port}")
    print(f"📦 Colección: {collection_name}\n")

    try:
        if not qdrant.collection_exists(collection_name):
            print("ℹ️  La colección no existe. No hay nada que limpiar.")
            return 0

        info = qdrant.get_collection_info(collection_name)
        if info and hasattr(info, "points_count"):
            print(f"📊 Puntos actuales en la colección: {info.points_count}")
        else:
            print("📊 La colección existe (no se pudo leer el conteo de puntos).")

        if not args.force:
            resp = input("\n⚠️  ¿Eliminar esta colección? Se perderán todos los vectores. [y/N]: ").strip().lower()
            if resp not in ("y", "yes", "s", "si"):
                print("Operación cancelada.")
                return 0

        if qdrant.delete_collection(collection_name):
            print("\n✅ Colección eliminada correctamente.")
            print("\n📌 Para una nueva carga masiva ejecuta:")
            print("   python -m src.etl.main --recreate")
            print("   (--recreate borra la colección y vuelve a crearla; si ya la borraste, usa -y)")
            return 0
        else:
            print("\n❌ No se pudo eliminar la colección.")
            return 1

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

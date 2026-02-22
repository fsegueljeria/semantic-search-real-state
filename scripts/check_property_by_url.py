#!/usr/bin/env python3
"""
Comprobar si una propiedad está en la base vectorial (Qdrant) por su URL
y mostrar todos los datos guardados para validar que estén bien.

Uso:
  python scripts/check_property_by_url.py
  python scripts/check_property_by_url.py "https://www.portalinmobiliario.com/MLC-3448621696-linda-y-acogedora-casa-en-umbrales-de-buin-_JM"
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from src.db.client import qdrant


# Primera propiedad del CSV de ejemplo
DEFAULT_URL = "https://www.portalinmobiliario.com/MLC-3448621696-linda-y-acogedora-casa-en-umbrales-de-buin-_JM"


def main():
    url = sys.argv[1].strip() if len(sys.argv) > 1 else DEFAULT_URL
    collection = settings.qdrant_collection_name

    print(f"Buscando en colección '{collection}' por URL:")
    print(f"  {url}\n")

    points = qdrant.get_points_by_payload(
        collection_name=collection,
        payload_filter={"url": url},
        limit=1,
    )

    if not points:
        print("❌ No se encontró ningún registro con esa URL en la base vectorial.")
        print("   Posibles causas: el ETL no se ha ejecutado, la colección está vacía o la URL no coincide exactamente.")
        sys.exit(1)

    point = points[0]
    payload = point.payload if hasattr(point, "payload") else point.get("payload", point)
    point_id = point.id if hasattr(point, "id") else point.get("id", "?")

    print("✅ Registro encontrado.\n")
    print("--- ID del punto (Qdrant) ---")
    print(point_id)
    print()
    print("--- Payload guardado (todos los datos) ---")
    # Ordenar y mostrar de forma legible
    for key in sorted(payload.keys()):
        val = payload[key]
        if key == "images" and isinstance(val, list):
            print(f"  {key}: [lista de {len(val)} URL(s)]")
            for i, u in enumerate(val[:3]):
                print(f"    [{i}] {u[:70]}...")
            if len(val) > 3:
                print(f"    ... y {len(val) - 3} más")
        elif isinstance(val, str) and len(val) > 100:
            print(f"  {key}: {val[:100]}...")
        else:
            print(f"  {key}: {val}")
    print()
    print("--- Payload completo (JSON) ---")
    # Serializar para que sea copiable (images como lista de URLs)
    out = {k: v for k, v in payload.items()}
    print(json.dumps(out, indent=2, ensure_ascii=False)[:2000])
    if len(json.dumps(out)) > 2000:
        print("... (truncado)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

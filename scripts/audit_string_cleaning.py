#!/usr/bin/env python3
"""
Auditoría de limpieza de strings
================================

Script para identificar registros con valores que no pudieron normalizarse
correctamente. Genera un reporte de filas/columnas a revisar o corregir manualmente.

Uso:
  python scripts/audit_string_cleaning.py [--csv RUTA] [--output REPORTE.csv] [--format csv|md]
"""

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

# Project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from config.settings import settings
from src.etl.loader import ETLLoader
from src.etl.cleaner import DataCleaner


# --- Validadores que devuelven (valor_limpio, problema_opcional) ---

def try_clean_numeric(raw: Any, default: float = 0.0) -> Tuple[float, Optional[str]]:
    """Intenta limpiar a número. Si falla, devuelve default y mensaje de problema."""
    if pd.isna(raw) or raw is None or raw == "":
        return default, None  # Vacío es aceptable
    raw_str = str(raw).strip()
    if not raw_str:
        return default, None
    try:
        cleaned = re.sub(r'[^\d\.,\-]', '', raw_str)
        if ',' in cleaned and '.' not in cleaned:
            cleaned = cleaned.replace(',', '.')
        elif cleaned.count(',') > 1 or (cleaned.count(',') == 1 and cleaned.count('.') == 1):
            cleaned = cleaned.replace(',', '')
        if not cleaned:
            return default, f"Sin dígitos extraíbles (original: {repr(raw_str)[:80]})"
        return float(cleaned), None
    except (ValueError, TypeError):
        return default, f"No convertible a número (original: {repr(raw_str)[:80]})"


def try_clean_price_uf(raw: Any) -> Tuple[float, Optional[str]]:
    """Valida PRECIO_UF: numérico y rango razonable."""
    val, num_issue = try_clean_numeric(raw, 0.0)
    if num_issue:
        return 0.0, num_issue
    if val < 0:
        return 0.0, f"Precio UF negativo ({val}); se usó 0"
    if val > 100000:
        return 100000.0, f"Precio UF extremo ({val}); se acotó a 100000"
    return val, None


def try_clean_coordinates(lat: Any, lon: Any) -> Tuple[Tuple[float, float], Optional[str]]:
    """Valida coordenadas dentro de Chile."""
    lat_val, lat_issue = try_clean_numeric(lat, 0.0)
    lon_val, lon_issue = try_clean_numeric(lon, 0.0)
    if lat_issue or lon_issue:
        return (0.0, 0.0), lat_issue or lon_issue
    if lat_val == 0.0 and lon_val == 0.0:
        return (lat_val, lon_val), None
    if not (-55 <= lat_val <= -17 and -109 <= lon_val <= -66):
        return (0.0, 0.0), f"Coordenadas fuera de Chile: ({lat_val}, {lon_val})"
    return (lat_val, lon_val), None


def try_parse_images_json(raw: Any) -> Tuple[List[str], Optional[str]]:
    """Intenta parsear IMAGES como JSON; devuelve lista de URLs o problema."""
    if pd.isna(raw) or not raw:
        return [], None
    s = str(raw).strip()
    if not s:
        return [], None
    try:
        fixed = s.replace('""', '"').replace('"{', '{').replace('}"', '}')
        data = json.loads(fixed)
        if isinstance(data, dict) and "images" in data:
            return data["images"], None
        if isinstance(data, list):
            return data, None
        return [], "JSON sin campo 'images' ni lista"
    except (json.JSONDecodeError, TypeError) as e:
        return [], f"JSON inválido: {str(e)[:60]}"


def check_semantic_blob(row: pd.Series) -> Tuple[str, Optional[str]]:
    """Genera el blob semántico y detecta si queda vacío o demasiado corto."""
    blob = DataCleaner.create_semantic_blob(row)
    if not blob or len(blob.strip()) < 10:
        return blob, "Contenido semántico insuficiente para embedding (título/descripción vacíos o muy cortos)"
    return blob, None


# --- Definición de columnas a auditar ---

NUMERIC_FIELDS = [
    ("PRECIO_UF", try_clean_price_uf),
    ("M2_UTIL", lambda x: try_clean_numeric(x, 0.0)),
    ("M2_TOTAL", lambda x: try_clean_numeric(x, 0.0)),
    ("DORMITORIOS", lambda x: try_clean_numeric(x, 0.0)),
    ("BANIOS", lambda x: try_clean_numeric(x, 0.0)),
    ("ESTACIONAMIENTO", lambda x: try_clean_numeric(x, 0.0)),
    ("BODEGA", lambda x: try_clean_numeric(x, 0.0)),
    ("PISO", lambda x: try_clean_numeric(x, 0.0)),
    ("ANIO", lambda x: try_clean_numeric(x, 0.0)),
    ("GASTOS_COMUNES", lambda x: try_clean_numeric(x, 0.0)),
]

COORD_FIELDS = ["LATITUD", "LONGITUD"]
IMAGES_FIELD = "IMAGES"
SEMANTIC_CHECK = "BLOB_SEMANTICO"  # virtual


def load_csv_as_dataframe(csv_path: Path) -> pd.DataFrame:
    """Carga el CSV con la misma lógica que el ETL (comillas externas + reagrupación)."""
    rows: List[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        header = [c.strip() for c in f.readline().strip().split(",")]
        for line in f:
            row = ETLLoader._parse_csv_row(line, header)
            if row:
                rows.append(row)
    return pd.DataFrame(rows)


def audit_row(row: pd.Series, row_index: int) -> List[dict]:
    """Audita una fila y devuelve lista de issues (dicts para el reporte)."""
    issues = []
    url = str(row.get("URL_PROPIEDAD", ""))[:120]

    for col, cleaner_fn in NUMERIC_FIELDS:
        if col not in row:
            continue
        raw = row[col]
        cleaned, problem = cleaner_fn(raw)
        if problem:
            issues.append({
                "row_index": row_index,
                "url": url,
                "column": col,
                "raw_value": _truncate(raw, 100),
                "issue_type": "numeric_invalid",
                "message": problem,
                "value_used": cleaned,
                "requires_manual_review": True,
            })

    lat, lon = row.get("LATITUD"), row.get("LONGITUD")
    (clat, clon), coord_problem = try_clean_coordinates(lat, lon)
    if coord_problem and (lat or lon):
        issues.append({
            "row_index": row_index,
            "url": url,
            "column": "LATITUD/LONGITUD",
            "raw_value": _truncate(f"({lat}, {lon})", 100),
            "issue_type": "coordinates_invalid",
            "message": coord_problem,
            "value_used": f"({clat}, {clon})",
            "requires_manual_review": True,
        })

    urls, img_problem = try_parse_images_json(row.get(IMAGES_FIELD))
    if img_problem and row.get(IMAGES_FIELD):
        issues.append({
            "row_index": row_index,
            "url": url,
            "column": IMAGES_FIELD,
            "raw_value": _truncate(row.get(IMAGES_FIELD), 80),
            "issue_type": "images_json_invalid",
            "message": img_problem,
            "value_used": "(lista vacía)",
            "requires_manual_review": True,
        })

    blob, blob_problem = check_semantic_blob(row)
    if blob_problem:
        issues.append({
            "row_index": row_index,
            "url": url,
            "column": SEMANTIC_CHECK,
            "raw_value": "(combinación título/descripción/comuna/otros)",
            "issue_type": "semantic_content_insufficient",
            "message": blob_problem,
            "value_used": "(blob vacío o muy corto)",
            "requires_manual_review": True,
        })

    return issues


def _truncate(val: Any, max_len: int) -> str:
    s = repr(val) if not isinstance(val, str) else val
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def run_audit(csv_path: Path) -> Tuple[pd.DataFrame, List[dict]]:
    """Carga el CSV, audita todas las filas y devuelve (df, lista de issues)."""
    df = load_csv_as_dataframe(csv_path)
    all_issues = []
    for idx, row in df.iterrows():
        all_issues.extend(audit_row(row, row_index=idx + 1))  # 1-based para lectura
    return df, all_issues


def write_report_csv(issues: List[dict], out_path: Path) -> None:
    """Escribe el reporte en CSV."""
    if not issues:
        out_path.write_text("row_index,url,column,raw_value,issue_type,message,value_used,requires_manual_review\n", encoding="utf-8")
        return
    cols = ["row_index", "url", "column", "raw_value", "issue_type", "message", "value_used", "requires_manual_review"]
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(issues)


def write_report_md(issues: List[dict], out_path: Path, csv_path: Path) -> None:
    """Escribe un resumen en Markdown."""
    lines = [
        "# Reporte de auditoría: limpieza de strings",
        "",
        f"**Archivo auditado:** `{csv_path}`",
        f"**Total de registros con problemas:** {len(set(i['row_index'] for i in issues))}",
        f"**Total de incidencias:** {len(issues)}",
        "",
        "## Resumen por tipo",
        "",
    ]
    from collections import Counter
    by_type = Counter(i["issue_type"] for i in issues)
    for t, count in by_type.most_common():
        lines.append(f"- `{t}`: {count}")
    lines.extend(["", "## Detalle (registros a corregir o revisar)", ""])
    # Agrupar por row_index
    by_row = {}
    for i in issues:
        by_row.setdefault(i["row_index"], []).append(i)
    for row_idx in sorted(by_row.keys()):
        items = by_row[row_idx]
        url = items[0]["url"] if items else ""
        lines.append(f"### Fila {row_idx} — {url[:70]}...")
        lines.append("")
        for it in items:
            lines.append(f"- **Columna:** {it['column']}")
            lines.append(f"  - Valor original: `{it['raw_value'][:80]}`")
            lines.append(f"  - Problema: {it['message']}")
            lines.append(f"  - Valor aplicado por cleaner: {it['value_used']}")
            lines.append("")
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Auditoría de limpieza de strings: identifica registros donde no se pudo establecer un valor correcto.",
        epilog="Tipos de incidencia: numeric_invalid, coordinates_invalid, images_json_invalid, semantic_content_insufficient.",
    )
    parser.add_argument("--csv", type=Path, default=Path(settings.csv_file_path), help="Ruta al CSV a auditar")
    parser.add_argument("--output", "-o", type=Path, default=Path("audit_cleaning_report.csv"), help="Archivo de salida del reporte")
    parser.add_argument("--format", choices=["csv", "md", "both"], default="both", help="Formato del reporte")
    parser.add_argument(
        "--exclude-types",
        nargs="+",
        metavar="TYPE",
        help="Excluir tipos de incidencia (ej: --exclude-types images_json_invalid)",
    )
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"Error: no se encuentra el archivo {args.csv}", file=sys.stderr)
        sys.exit(1)

    print(f"Cargando y auditando {args.csv}...")
    df, issues = run_audit(args.csv)
    if args.exclude_types:
        excluded = set(args.exclude_types)
        issues = [i for i in issues if i["issue_type"] not in excluded]
        print(f"Excluidos tipos: {excluded}. Incidencias restantes: {len(issues)}.")
    print(f"Filas cargadas: {len(df)}. Incidencias detectadas: {len(issues)}.")

    if args.format in ("csv", "both"):
        out_csv = args.output if args.output.suffix.lower() == ".csv" else args.output.with_suffix(".csv")
        write_report_csv(issues, out_csv)
        print(f"Reporte CSV: {out_csv}")
    if args.format in ("md", "both"):
        out_md = args.output if args.output.suffix.lower() == ".md" else args.output.with_suffix(".md")
        write_report_md(issues, out_md, args.csv)
        print(f"Reporte Markdown: {out_md}")

    if issues:
        print("\nRegistros con al menos un problema (revisar reporte):", sorted(set(i["row_index"] for i in issues)))
    else:
        print("No se detectaron valores que requieran corrección manual.")


if __name__ == "__main__":
    main()

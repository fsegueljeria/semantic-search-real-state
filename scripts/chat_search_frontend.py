#!/usr/bin/env python3
"""
Frontend tipo chat para búsqueda semántica de propiedades.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from scripts.semantic_search import extract_filters
from src.db.client import qdrant
from src.services.embedder import embedder


def _get_score_and_payload(hit: Any) -> Tuple[float, Dict[str, Any]]:
    """Normaliza resultado de Qdrant a score + payload."""
    if hasattr(hit, "score"):
        score = float(hit.score)
        payload = hit.payload if hasattr(hit, "payload") else {}
        return score, payload or {}
    return float(hit.get("score", 0.0)), hit.get("payload", hit)


def _normalize_images(images: Any) -> List[str]:
    """Obtiene lista de URLs de fotos desde distintos formatos."""
    if not images:
        return []

    if isinstance(images, str):
        try:
            images = json.loads(images)
        except json.JSONDecodeError:
            return []

    if isinstance(images, dict) and "images" in images:
        images = images["images"]

    if isinstance(images, list):
        return [str(url) for url in images if str(url).strip()]

    return []


def _search_properties(query: str, top_k: int, score_threshold: float) -> Dict[str, Any]:
    """Ejecuta búsqueda semántica + filtros sobre Qdrant."""
    query_clean, filters = extract_filters(query)
    vector = embedder.embed_text(query_clean if query_clean else query)

    results = qdrant.search_similar(
        collection_name=settings.qdrant_collection_name,
        query_vector=vector,
        limit=top_k,
        metadata_filter=filters if filters else None,
        score_threshold=score_threshold if score_threshold > 0 else None,
    )

    normalized_results = []
    for hit in results:
        score, payload = _get_score_and_payload(hit)
        payload["images"] = _normalize_images(payload.get("images"))
        normalized_results.append({"score": score, "payload": payload})

    return {
        "query": query,
        "query_clean": query_clean,
        "filters": filters,
        "results": normalized_results,
    }


# Altura del placeholder cuando no hay imagen; tarjetas por fila en la cuadrícula
CARD_IMAGE_HEIGHT = 140
CARDS_PER_ROW = 3


def _render_images_carousel(images: List[str], carousel_key: str) -> None:
    """Renderiza un carrusel de fotos dentro de un expander (no ocupa espacio por defecto)."""
    if not images:
        return

    idx_key = f"{carousel_key}_idx"
    if idx_key not in st.session_state:
        st.session_state[idx_key] = 0

    current_idx = int(st.session_state[idx_key])
    current_idx = max(0, min(current_idx, len(images) - 1))
    st.session_state[idx_key] = current_idx

    col_prev, col_counter, col_next = st.columns([1, 6, 1])
    with col_prev:
        if st.button("⬅️", key=f"{carousel_key}_prev", use_container_width=True):
            st.session_state[idx_key] = (current_idx - 1) % len(images)
    with col_counter:
        st.markdown(
            f"<div style='text-align:center;'>Foto {current_idx + 1} de {len(images)}</div>",
            unsafe_allow_html=True,
        )
    with col_next:
        if st.button("➡️", key=f"{carousel_key}_next", use_container_width=True):
            st.session_state[idx_key] = (current_idx + 1) % len(images)

    current_idx = int(st.session_state[idx_key])
    st.image(images[current_idx], use_container_width=True)


def _render_property_card_compact(item: Dict[str, Any], index: int, card_key: str) -> None:
    """
    Tarjeta compacta al estilo listado: miniatura pequeña, tipo, ubicación, precio, dorm|baños|m².
    Descripción y galería de fotos quedan dentro de un expander 'Ver más'.
    """
    payload = item["payload"]
    score = item["score"]

    title = payload.get("titulo") or f"Propiedad #{index}"
    comuna = payload.get("comuna", "No especificada")
    barrio = payload.get("barrio", "")
    tipo = (payload.get("tipo_propiedad") or "N/A").capitalize()
    operacion = payload.get("operacion", "N/A")
    precio = payload.get("precio_uf", 0)
    try:
        precio_str = f"{float(precio):,.0f}" if precio not in ("N/A", None) else "N/A"
    except (TypeError, ValueError):
        precio_str = str(precio)
    dormitorios = payload.get("dormitorios", "N/A")
    banios = payload.get("banios", "N/A")
    m2_util = payload.get("m2_util", "N/A")
    m2_total = payload.get("m2_total", "N/A")
    url = payload.get("url", "")
    images = payload.get("images", [])

    with st.container(border=True):
        # Fila: miniatura a la izquierda, datos a la derecha
        col_img, col_info = st.columns([1, 2])
        with col_img:
            if images:
                st.image(
                    images[0],
                    use_container_width=True,
                    caption="",
                )
            else:
                st.markdown(
                    f"<div style='height:{CARD_IMAGE_HEIGHT}px; background:#f0f0f0; "
                    "display:flex; align-items:center; justify-content:center; border-radius:8px;'>"
                    "<span style='color:#888;'>Sin imagen</span></div>",
                    unsafe_allow_html=True,
                )
        with col_info:
            st.markdown(f"**{tipo}** · {operacion}")
            ubicacion = f"{comuna}" + (f", {barrio}" if barrio else "")
            st.caption(f"📍 {ubicacion}")
            st.markdown(f"**UF {precio_str}**")
            st.caption(f"🛏️ {dormitorios} dorm · 🚿 {banios} baños · 📐 {m2_total} m² totales")

        if url:
            st.markdown(f"[Abrir publicación]({url})")

        with st.expander("Ver descripción y fotos"):
            descripcion = payload.get("descripcion", "")
            if descripcion:
                st.markdown("**Descripción completa**")
                st.write(descripcion[:800] + ("..." if len(descripcion) > 800 else ""))
            if images:
                st.markdown(f"**Fotos ({len(images)})**")
                _render_images_carousel(images, carousel_key=f"{card_key}_carousel")
            st.caption(f"Relevancia: {score:.4f}")


def main() -> None:
    st.set_page_config(
        page_title="Chat de Búsqueda Inmobiliaria",
        page_icon="🏠",
        layout="wide",
    )

    st.title("🏠 Chat de Búsqueda Semántica")
    st.write("Busca propiedades en lenguaje natural y recibe resultados con fotos.")

    with st.sidebar:
        st.subheader("Configuración")
        top_k = st.slider("Cantidad de resultados", min_value=3, max_value=15, value=5)
        score_threshold = st.slider(
            "Umbral mínimo de relevancia",
            min_value=0.0,
            max_value=1.0,
            value=0.0,
            step=0.05,
        )
        st.caption(f"Colección activa: `{settings.qdrant_collection_name}`")
        st.caption(f"Modelo embeddings: `{settings.embedding_model}`")

    if "history" not in st.session_state:
        st.session_state.history = []

    for turn_idx, turn in enumerate(st.session_state.history):
        with st.chat_message("user"):
            st.write(turn["query"])
        with st.chat_message("assistant"):
            n = len(turn["results"])
            st.markdown(
                f"He encontrado **{n} propiedades** aplicando los criterios: **{turn['query']}**."
            )
            if turn["filters"]:
                st.caption(f"Filtros: {turn['filters']}")
            st.markdown("---")
            # Cuadrícula de tarjetas compactas (varias por fila)
            for start in range(0, n, CARDS_PER_ROW):
                chunk = turn["results"][start : start + CARDS_PER_ROW]
                cols = st.columns(min(len(chunk), CARDS_PER_ROW))
                for col_idx, (col, item) in enumerate(zip(cols, chunk)):
                    with col:
                        _render_property_card_compact(
                            item, start + col_idx + 1, card_key=f"history_{turn_idx}_{start}_{col_idx}"
                        )

    prompt = st.chat_input(
        "Ej: casa en Buin con jardín, 4 dormitorios y menos de 6000 UF"
    )
    if not prompt:
        return

    with st.chat_message("user"):
        st.write(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Buscando propiedades..."):
            response = _search_properties(prompt, top_k=top_k, score_threshold=score_threshold)

        if not response["results"]:
            st.warning("No encontré propiedades con esos criterios. Prueba una consulta más amplia.")
        else:
            n = len(response["results"])
            st.markdown(
                f"He encontrado **{n} propiedades** aplicando los criterios: **{response['query']}**."
            )
            if response["filters"]:
                st.caption(f"Filtros: {response['filters']}")
            st.markdown("---")
            # Cuadrícula de tarjetas compactas
            for start in range(0, n, CARDS_PER_ROW):
                chunk = response["results"][start : start + CARDS_PER_ROW]
                cols = st.columns(min(len(chunk), CARDS_PER_ROW))
                for col_idx, (col, item) in enumerate(zip(cols, chunk)):
                    with col:
                        _render_property_card_compact(
                            item, start + col_idx + 1,
                            card_key=f"current_{len(st.session_state.history)}_{start}_{col_idx}",
                        )

    st.session_state.history.append(response)


if __name__ == "__main__":
    main()

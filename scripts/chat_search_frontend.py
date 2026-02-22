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


def _render_images_carousel(images: List[str], carousel_key: str) -> None:
    """Renderiza un carrusel simple con navegación anterior/siguiente."""
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

    with st.expander("Ver todas las URLs de fotos"):
        for i, img_url in enumerate(images, 1):
            st.write(f"{i}. {img_url}")


def _render_property_card(item: Dict[str, Any], index: int, card_key: str) -> None:
    """Renderiza una propiedad en formato tarjeta."""
    payload = item["payload"]
    score = item["score"]

    title = payload.get("titulo") or f"Propiedad #{index}"
    comuna = payload.get("comuna", "No especificada")
    tipo = payload.get("tipo_propiedad", "N/A")
    operacion = payload.get("operacion", "N/A")
    precio = payload.get("precio_uf", 0)
    dormitorios = payload.get("dormitorios", "N/A")
    banios = payload.get("banios", "N/A")
    m2_util = payload.get("m2_util", "N/A")
    m2_total = payload.get("m2_total", "N/A")
    url = payload.get("url", "")
    images = payload.get("images", [])

    with st.container(border=True):
        st.markdown(f"### {index}. {title}")
        st.caption(f"Relevancia: {score:.4f}")
        st.markdown(
            f"**{tipo}** en **{operacion}** · 📍 {comuna} · 💰 {precio:.2f} UF"
        )
        st.markdown(
            f"🛏️ {dormitorios} dormitorios · 🚿 {banios} baños · "
            f"📐 {m2_util} m² útiles · 📐 {m2_total} m² totales"
        )

        descripcion = payload.get("descripcion", "")
        if descripcion:
            st.markdown("**Descripción completa**")
            st.write(descripcion)

        if url:
            st.markdown(f"[Abrir publicación]({url})")

        if images:
            st.markdown(f"**Fotos ({len(images)})**")
            _render_images_carousel(images, carousel_key=f"{card_key}_carousel")


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
            filters = turn["filters"]
            if filters:
                st.write(f"Filtros detectados: {filters}")
            if turn["query_clean"] and turn["query_clean"] != turn["query"]:
                st.write(f"Query semántica: `{turn['query_clean']}`")
            st.write(f"Resultados: {len(turn['results'])}")
            for idx, item in enumerate(turn["results"], 1):
                _render_property_card(item, idx, card_key=f"history_{turn_idx}_{idx}")

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

        if response["filters"]:
            st.write(f"Filtros detectados: {response['filters']}")
        if response["query_clean"] and response["query_clean"] != prompt:
            st.write(f"Query semántica: `{response['query_clean']}`")

        if not response["results"]:
            st.warning("No encontré propiedades con esos criterios. Prueba una consulta más amplia.")
        else:
            st.success(f"Encontré {len(response['results'])} propiedades relevantes.")
            for idx, item in enumerate(response["results"], 1):
                _render_property_card(item, idx, card_key=f"current_{len(st.session_state.history)}_{idx}")

    st.session_state.history.append(response)


if __name__ == "__main__":
    main()

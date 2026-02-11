"""
Data Cleaning and Preprocessing
==============================

Utilities for cleaning and preparing real estate data for vector indexing.
"""

import re
import json
import sys
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np
from unidecode import unidecode
from loguru import logger
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings


class DataCleaner:
    """Data cleaning and preprocessing utilities."""
    
    @staticmethod
    def clean_string(text: Any) -> str:
        """Clean and normalize string data."""
        if pd.isna(text) or text is None:
            return ""
        
        # Convert to string
        text = str(text)
        
        # Handle description field specifically (remove array brackets and extra quotes)
        if text.startswith('"[') and text.endswith(']"'):
            # Remove outer quotes and brackets
            text = text[2:-2]
            # Handle escaped quotes
            text = text.replace('"""', '"').replace('\\n', ' ')
        
        # Remove unicode characters and normalize
        text = unidecode(text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s\.,!?\-\(\)]', ' ', text)
        
        # Strip and normalize case
        text = text.strip()
        
        return text
    
    @staticmethod
    def clean_numeric(value: Any, default: float = 0.0) -> float:
        """Clean and convert numeric values."""
        if pd.isna(value) or value is None or value == "":
            return default
        
        try:
            # Handle string representations
            if isinstance(value, str):
                # Remove common separators and symbols
                value = re.sub(r'[^\d\.,\-]', '', value)
                # Handle comma as decimal separator (Chilean format)
                if ',' in value and '.' not in value:
                    value = value.replace(',', '.')
                # Remove thousands separators
                elif value.count(',') > 1 or (value.count(',') == 1 and value.count('.') == 1):
                    value = value.replace(',', '')
            
            return float(value)
        except (ValueError, TypeError):
            logger.warning(f"Could not convert '{value}' to numeric, using default: {default}")
            return default
    
    @staticmethod
    def clean_price_uf(value: Any) -> float:
        """Clean and normalize UF price values."""
        cleaned = DataCleaner.clean_numeric(value, 0.0)
        
        # Handle extreme outliers (likely data errors)
        if cleaned < 0:
            return 0.0
        elif cleaned > 100000:  # UF prices above 100k are suspicious
            logger.warning(f"Extreme UF price detected: {cleaned}, capping at 100000")
            return 100000.0
        
        return cleaned
    
    @staticmethod
    def clean_coordinates(lat: Any, lon: Any) -> tuple[float, float]:
        """Clean and validate coordinate values."""
        clean_lat = DataCleaner.clean_numeric(lat, 0.0)
        clean_lon = DataCleaner.clean_numeric(lon, 0.0)
        
        # If both are zero, that's acceptable (missing coordinates)
        if clean_lat == 0.0 and clean_lon == 0.0:
            return 0.0, 0.0
        
        # Validate Chilean coordinate ranges only if not zero
        # Chile approximate bounds: lat -55 to -17, lon -109 to -66
        if not (-55 <= clean_lat <= -17 and -109 <= clean_lon <= -66):
            logger.debug(f"Coordinates out of Chile bounds, setting to zero: ({clean_lat}, {clean_lon})")
            return 0.0, 0.0
        
        return clean_lat, clean_lon
    
    @staticmethod
    def parse_images_json(images_str: Any) -> List[str]:
        """Parse and extract image URLs from JSON string."""
        if pd.isna(images_str) or not images_str:
            return []
        
        try:
            # Handle both string and already parsed JSON
            if isinstance(images_str, str):
                # Fix common JSON formatting issues
                images_str = images_str.replace('""', '"').replace('"{', '{').replace('}"', '}')
                images_data = json.loads(images_str)
            else:
                images_data = images_str
            
            # Extract image URLs
            if isinstance(images_data, dict) and "images" in images_data:
                return images_data["images"]
            elif isinstance(images_data, list):
                return images_data
            else:
                return []
                
        except (json.JSONDecodeError, TypeError) as e:
            logger.debug(f"Could not parse images JSON: {e}")
            return []
    
    @staticmethod
    def create_semantic_blob(row: pd.Series) -> str:
        """Create unified text for semantic embedding."""
        components = []
        
        # Add title with higher weight (repeat 2x for importance)
        title = DataCleaner.clean_string(row.get('TITULO_PROPIEDAD', ''))
        if title:
            components.extend([title, title])
        
        # Add location information
        comuna = DataCleaner.clean_string(row.get('COMUNA', ''))
        barrio = DataCleaner.clean_string(row.get('BARRIO', ''))
        if comuna:
            components.append(f"Comuna {comuna}")
        if barrio:
            components.append(f"Barrio {barrio}")
        
        # Add property type and operation
        tipo = DataCleaner.clean_string(row.get('TIPO_PROPIEDAD', ''))
        operacion = DataCleaner.clean_string(row.get('OPERACION', ''))
        if tipo:
            components.append(f"{tipo}")
        if operacion:
            components.append(f"en {operacion}")
        
        # Add room information
        dormitorios = DataCleaner.clean_numeric(row.get('DORMITORIOS', 0))
        banios = DataCleaner.clean_numeric(row.get('BANIOS', 0))
        if dormitorios > 0:
            components.append(f"{int(dormitorios)} dormitorios")
        if banios > 0:
            components.append(f"{int(banios)} baños")
        
        # Add size information
        m2_util = DataCleaner.clean_numeric(row.get('M2_UTIL', 0))
        if m2_util > 0:
            components.append(f"{int(m2_util)} metros cuadrados útiles")
        
        # Add amenities
        estacionamiento = DataCleaner.clean_numeric(row.get('ESTACIONAMIENTO', 0))
        bodega = DataCleaner.clean_numeric(row.get('BODEGA', 0))
        if estacionamiento > 0:
            components.append("con estacionamiento")
        if bodega > 0:
            components.append("con bodega")
        
        # Add description (most important semantic content)
        descripcion = DataCleaner.clean_string(row.get('DESCRIPCION', ''))
        if descripcion:
            # Truncate description if too long
            if len(descripcion) > 1000:
                descripcion = descripcion[:1000] + "..."
            components.append(descripcion)
        
        # Join all components
        semantic_text = " ".join(components)
        
        # Final cleaning and length check
        semantic_text = DataCleaner.clean_string(semantic_text)
        
        # Ensure reasonable length for embedding model
        if len(semantic_text) > 2000:
            semantic_text = semantic_text[:2000] + "..."
        
        return semantic_text
    
    @staticmethod
    def prepare_metadata(row: pd.Series) -> Dict[str, Any]:
        """Prepare metadata payload for vector storage."""
        metadata = {}
        
        # Basic info
        metadata['url'] = str(row.get('URL_PROPIEDAD', ''))
        metadata['portal'] = DataCleaner.clean_string(row.get('PORTAL', ''))
        metadata['tipo_propiedad'] = DataCleaner.clean_string(row.get('TIPO_PROPIEDAD', ''))
        metadata['operacion'] = DataCleaner.clean_string(row.get('OPERACION', ''))
        
        # Location
        metadata['comuna'] = DataCleaner.clean_string(row.get('COMUNA', ''))
        metadata['barrio'] = DataCleaner.clean_string(row.get('BARRIO', ''))
        lat, lon = DataCleaner.clean_coordinates(row.get('LATITUD'), row.get('LONGITUD'))
        metadata['latitud'] = lat
        metadata['longitud'] = lon
        
        # Price and size
        metadata['precio_uf'] = DataCleaner.clean_price_uf(row.get('PRECIO_UF'))
        metadata['m2_util'] = DataCleaner.clean_numeric(row.get('M2_UTIL'))
        metadata['m2_total'] = DataCleaner.clean_numeric(row.get('M2_TOTAL'))
        
        # Property details
        metadata['dormitorios'] = int(DataCleaner.clean_numeric(row.get('DORMITORIOS')))
        metadata['banios'] = int(DataCleaner.clean_numeric(row.get('BANIOS')))
        metadata['estacionamiento'] = int(DataCleaner.clean_numeric(row.get('ESTACIONAMIENTO')))
        metadata['bodega'] = int(DataCleaner.clean_numeric(row.get('BODEGA')))
        
        # Additional info
        metadata['anio'] = int(DataCleaner.clean_numeric(row.get('ANIO'), 0))
        metadata['piso'] = int(DataCleaner.clean_numeric(row.get('PISO'), 0))
        metadata['gastos_comunes'] = DataCleaner.clean_numeric(row.get('GASTOS_COMUNES'))
        
        # Text fields
        metadata['titulo'] = DataCleaner.clean_string(row.get('TITULO_PROPIEDAD', ''))[:500]
        metadata['descripcion'] = DataCleaner.clean_string(row.get('DESCRIPCION', ''))[:1000]
        
        # Images
        metadata['images'] = DataCleaner.parse_images_json(row.get('IMAGES'))
        metadata['n_images'] = len(metadata['images'])
        
        return metadata
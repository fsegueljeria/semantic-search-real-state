import pandas as pd
import io

# Crear un pequeño CSV con la fila problemática
csv_data = """"2026-01-15 21:19:10.362911-03,https://www.portalinmobiliario.com/MLC-3458340654-se-vende-promesa-de-compraventa-100-uf-departamento-1d1b-_JM,Portal Inmobiliario,departamento,Venta,Las Condes,,-33.5280201,-70.592055,379,33,36,1,1,,,https://www.portalinmobiliario.com/venta/departamento/propiedades-usadas/la-florida-metropolitana#applied_filter_id%3Dcity%26applied_filter_name%3DCiudades%26applied_filter_order%3D1%26applied_value_id%3DTUxDQ0xBIGM5NzMz%26applied_value_name%3DLa+Florida%26applied_value_order%3D14%26applied_value_results%3D1645%26is_custom%3Dfalse%26view_more_flag%3Dtrue,14,5,1,1,,,,2026,Se Vende Promesa De Compraventa 100 Uf  Departamento 1d/1b,""{""""n_img"""": 3, """"images"""": [""""https://http2.mlstatic.com/D_NQ_NP_821677-MLC83621697677_042025-F-se-vende-promesa-de-compraventa-100-uf-departamento-1d1b.webp"""",""""https://http2.mlstatic.com/frontend-assets/vis-transactions-frontend/little-empty-state.webp"""",""""https://http2.mlstatic.com/frontend-assets/vis-transactions-frontend/little-empty-state.webp""""]}"",""['¡Imperdible oportunidad de inversión en proyecto en construcción! Se vende promesa de compraventa de moderno departamento de 1 dormitorio y 1 baño, que incluye bodega y estacionamiento, en edificio con excelentes espacios comunes. Ideal para vivir o invertir.\\n\\n -Ubicación: Proyecto Eco Valdés II Inmobiliaria Fundamenta\\n -Entrega estimada: Segundo semestre de 2026\\n -Valor total del departamento: 3.226 UF\\n -Pie pagado: 100 UF (Lo que debe pagar el comprador al vendedor)\\n -Saldo pendiente con la inmobiliaria: 17 cuotas mensuales de 2,32 UF, correspondientes al resto del pie. Todas las cuotas están pagadas al día.\\n* Pie pagado más saldo pendiente equivale al 10% del valor total del depto.\\n\\nSi necesitas que te explique como se traspasa la promesas y sus valores ($) no tengo problema.\\n\\n-Características del departamento:\\n\\n1 dormitorio amplio\\n\\n1 baño completo\\n\\nCocina americana\\n\\nBodega\\n\\nEstacionamiento\\n\\nExcelentes terminaciones y distribución\\n\\n-Áreas comunes del proyecto:\\n\\nPiscina\\n\\nGimnasio equipado\\n\\nQuinchos\\n\\nSalón de eventos\\n\\nSeguridad 24/7\\n\\n- Proyecto en obra, con alta plusvalía proyectada. Entrega estimada para el segundo semestre de 2026.']"
"""

try:
    # Intento 1: Carga estándar de Pandas
    print("Intento 1: Carga estándar")
    df = pd.read_csv(io.StringIO(csv_data), header=None)
    print(f"Columnas detectadas: {len(df.columns)}")
    print(df.iloc[0].values)
    
except Exception as e:
    print(f"Error Intento 1: {e}")

try:
    # Intento 2: Carga con quoting=3 (QUOTE_NONE) y escapechar='\\' como en loader.py
    print("\nIntento 2: Carga con configuración actual (quoting=3, escapechar='\\\\')")
    df = pd.read_csv(
        io.StringIO(csv_data), 
        header=None,
        quoting=3,
        escapechar='\\',
        on_bad_lines='warn'
    )
    print(f"Columnas detectadas: {len(df.columns)}")
    # Mapeo manual basado en las columnas esperadas
    cols = [
        "EXECUTION_TIME", "URL_PROPIEDAD", "PORTAL", "TIPO_PROPIEDAD", "OPERACION", 
        "COMUNA", "BARRIO", "LATITUD", "LONGITUD", "PRECIO_UF", "M2_UTIL", "M2_TOTAL", 
        "DORMITORIOS", "BANIOS", "CORREDORA", "CODIGO_INTERNO", "URL_PLP", "POSICION", 
        "SELLER_THERMOMETER", "ESTACIONAMIENTO", "BODEGA", "ORIENTACION", "GASTOS_COMUNES", 
        "PISO", "ANIO", "TITULO_PROPIEDAD", "IMAGES", "DESCRIPCION"
    ]
    
    # Mostrar índices y valores
    values = df.iloc[0].values
    for i, val in enumerate(values):
        col_name = cols[i] if i < len(cols) else f"UNKNOWN_{i}"
        print(f"{i}: {col_name} -> {val}")

except Exception as e:
    print(f"Error Intento 2: {e}")

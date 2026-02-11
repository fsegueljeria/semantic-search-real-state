import pandas as pd
from src.etl.cleaner import DataCleaner

def test_data_cleaning():
    print("Iniciando prueba de limpieza de datos...")
    
    # Simular una fila con datos similares a los del CSV
    data = {
        'URL_PROPIEDAD': 'http://example.com',
        'PORTAL': 'Portal Inmobiliario',
        'TIPO_PROPIEDAD': 'Departamento',
        'OPERACION': 'Venta',
        'COMUNA': 'Se Vende Promesa De Compraventa 100 Uf Departamento 1d 1b', # Valor incorrecto
        'BARRIO': 'n_img      3', # Valor incorrecto
        'LATITUD': None,
        'LONGITUD': None,
        'PRECIO_UF': '0.0',
        'M2_UTIL': '11.0',
        'M2_TOTAL': '0.0',
        'DORMITORIOS': '0',
        'BANIOS': '32', # El valor problemático
        'ESTACIONAMIENTO': '0',
        'BODEGA': '0',
        'ANIO': '0',
        'PISO': '0',
        'GASTOS_COMUNES': '0',
        'TITULO_PROPIEDAD': 'Titulo de prueba',
        'DESCRIPCION': 'Descripcion de prueba',
        'IMAGES': '[]'
    }
    
    row = pd.Series(data)
    
    # Probar la limpieza de metadatos
    metadata = DataCleaner.prepare_metadata(row)
    
    print("\nResultados de metadatos:")
    for key, value in metadata.items():
        print(f"{key}: {value}")

    # Probar específicamente clean_numeric con el valor problemático
    banio_value = '32'
    cleaned_banio = DataCleaner.clean_numeric(banio_value)
    print(f"\nValor original baños: '{banio_value}'")
    print(f"Valor limpio baños: {cleaned_banio}")

if __name__ == "__main__":
    test_data_cleaning()
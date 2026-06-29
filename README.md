# Dashboard BCRP - Streamlit

Este paquete convierte el dashboard originalmente trabajado en Power BI a una versión publicable en Streamlit, para cumplir con la entrega final del Laboratorio de Datos Sociales.

## Archivos principales

- `app.py`: dashboard interactivo en Python/Streamlit.
- `data/bcrp_data_limpia.csv`: base limpia normalizada a formato largo.
- `data/bcrp_series_metadata.csv`: diccionario de indicadores y fuentes.
- `requirements.txt`: librerías necesarias para ejecutar o publicar la aplicación.

## Ejecución local

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Publicación sugerida

1. Subir esta carpeta a GitHub.
2. Crear una app en Streamlit Community Cloud.
3. Seleccionar el repositorio, el archivo `app.py` y publicar.
4. Copiar el enlace público en el documento final.

## Notas

La app funciona con la base local incluida. También tiene un interruptor para intentar actualizar la información desde la API oficial del BCRP cuando haya conexión a internet.

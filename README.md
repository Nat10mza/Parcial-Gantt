# Simulador de planificación de CPU

Algoritmos: FIFO, SJF (sin desalojo), SRTF (con desalojo) y Round Robin.

## Requisitos

Python 3.10 o superior.

## Instalación (una sola vez)

macOS / Linux:

```
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Windows (PowerShell o CMD):

```
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

## Ejecutar la interfaz gráfica

macOS / Linux:

```
.venv/bin/streamlit run app.py
```

Windows:

```
.venv\Scripts\streamlit run app.py
```

Se abre en el navegador en http://localhost:8501. Para cortarla: Ctrl+C en la terminal.

## Ejecutar por consola (sin interfaz)

Cada algoritmo también corre solo, pidiendo los datos por teclado:

```
python3 simulador_sjf.py
```

## Problemas comunes

- **La primera vez Streamlit pide un email:** dejalo vacío y apretá Enter.
- **`python3` / `py` no existe:** instalá Python desde https://www.python.org/downloads/ (en Windows, marcar "Add Python to PATH").

"""Interfaz gráfica (Streamlit) para los simuladores de planificación.

Ejecutar con:  .venv/bin/streamlit run app.py
"""
import html
import importlib.util
import math
from pathlib import Path

import pandas as pd
import streamlit as st

CARPETA = Path(__file__).parent
INTERVALO = 10  # 1 casilla del cuadro = 10 ut = 1 quantum


def cargar_modulo(nombre_archivo):
    # importlib porque "simulador_fifo (1).py" no es un nombre importable
    spec = importlib.util.spec_from_file_location(nombre_archivo, CARPETA / nombre_archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@st.cache_resource
def cargar_algoritmos():
    fifo = cargar_modulo("simulador_fifo (1).py")
    sjf = cargar_modulo("simulador_sjf.py")
    srtf = cargar_modulo("simulador_srtf.py")
    rr = cargar_modulo("simulador_round_robin.py")
    # nombre -> (módulo, clase del simulador, usa quantum)
    return {
        "FIFO": (fifo, fifo.SimuladorOSFIFO, False),
        "SJF (sin desalojo)": (sjf, sjf.SimuladorOSSJF, False),
        "SRTF (con desalojo)": (srtf, srtf.SimuladorOSSRTF, False),
        "Round Robin": (rr, rr.SimuladorOSRoundRobin, True),
    }


def simular(nombre, filas, duracion_es, quantum, tiempo_max):
    modulo, clase, usa_quantum = cargar_algoritmos()[nombre]
    # Procesos nuevos en cada corrida: el simulador los modifica
    procesos = [modulo.Proceso(f["id"], f["llegada"], list(f["rafagas"])) for f in filas]
    if usa_quantum:
        sim = clase(procesos, duracion_es, quantum, tiempo_max=tiempo_max, intervalo=INTERVALO)
    else:
        sim = clase(procesos, duracion_es, tiempo_max=tiempo_max, intervalo=INTERVALO)
    sim.ejecutar()
    return sim


def calcular_metricas(sim):
    # Todo expresado en quantums (casillas de 10 ut).
    # Retorno = (instante en que figura Terminado - llegada) / intervalo
    # Espera  = casillas en estado Listo
    fin = {pid.lower(): tv for (tv, pid) in sim.terminados}
    filas = []
    for p_id, p in sorted(sim.procesos.items()):
        espera = sum(1 for t in sim.tiempos if sim.snapshots[t].get(p_id) == "Listo")
        termino = p_id in fin
        filas.append({
            "Proceso": p_id.upper(),
            "Llegada (ut)": p.llegada,
            "Fin (ut)": fin[p_id] if termino else None,
            "Retorno (q)": (fin[p_id] - p.llegada) / sim.intervalo if termino else None,
            "Espera (q)": espera if termino else None,
        })
    return pd.DataFrame(filas)


def parsear_procesos(df):
    filas, errores, vistos = [], [], set()
    for i, fila in df.iterrows():
        n = i + 1
        p_id = str(fila.get("ID") or "").strip().lower() or f"p{n}"
        if p_id in vistos:
            errores.append(f"Fila {n}: el ID {p_id.upper()} está repetido.")
            continue
        vistos.add(p_id)
        try:
            llegada = int(fila.get("Llegada (ut)"))
        except (TypeError, ValueError):
            errores.append(f"Fila {n}: la llegada debe ser un número entero.")
            continue
        texto = str(fila.get("Ráfagas CPU (ut)") or "")
        try:
            rafagas = [int(x) for x in texto.replace(";", ",").split(",") if x.strip()]
        except ValueError:
            errores.append(f"Fila {n}: las ráfagas deben ser números separados por coma (ej. 30, 20).")
            continue
        if not rafagas or any(r <= 0 for r in rafagas):
            errores.append(f"Fila {n}: ingresá al menos una ráfaga mayor que 0.")
            continue
        filas.append({"id": p_id, "llegada": llegada, "rafagas": rafagas})
    return filas, errores


def quantum_regla_80(filas):
    # Menor quantum (múltiplo de INTERVALO) con el que al menos el 80% de las
    # ráfagas de CPU terminan dentro de un solo quantum.
    rafagas = sorted(r for f in filas for r in f["rafagas"])
    total = len(rafagas)
    necesarias = math.ceil(0.8 * total)
    quantum = math.ceil(rafagas[necesarias - 1] / INTERVALO) * INTERVALO
    cubiertas = sum(1 for r in rafagas if r <= quantum)
    return quantum, cubiertas, total


COLORES = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#72B7B2", "#B279A2", "#FF9DA6", "#9D755D"]


def cuadro_html(sim):
    ids = sorted(sim.procesos.keys(), reverse=True)  # p4 arriba, p1 abajo, como la plantilla
    color = {p_id: COLORES[i % len(COLORES)] for i, p_id in enumerate(sorted(sim.procesos))}

    def celda(texto="", fondo=None, clase=""):
        estilo = f' style="background:{fondo}33;"' if fondo else ""
        return f'<td class="{clase}"{estilo}>{html.escape(str(texto))}</td>'

    def fila(etiqueta, celdas, clase_fila=""):
        return f'<tr class="{clase_fila}"><th>{etiqueta}</th>{"".join(celdas)}</tr>'

    def seccion_por_proceso(titulo, estado, marca_fondo):
        filas = [fila(titulo, [celda() for _ in sim.tiempos], "titulo")]
        for p_id in ids:
            celdas = []
            for t in sim.tiempos:
                activo = sim.snapshots[t].get(p_id) == estado
                celdas.append(celda("x" if activo else "", color[p_id] if activo and marca_fondo else None))
            filas.append(fila(f"&nbsp;&nbsp;{p_id.upper()}", celdas))
        return filas

    filas = [fila("Terminado", [celda(sim.matriz_terminado[t]) for t in sim.tiempos])]
    filas += seccion_por_proceso("Bloqueado", "Bloqueado", True)
    filas.append(fila("Ejecutando", [
        celda(sim.matriz_ejecutando[t], color.get(sim.matriz_ejecutando[t].lower()), "ejec")
        for t in sim.tiempos
    ]))
    filas += seccion_por_proceso("Listo", "Listo", True)
    filas.append(fila("S. Operativo", [celda(sim.eventos_so[t], clase="so") for t in sim.tiempos]))
    filas.append(fila("Tiempo", [celda(t, clase="tiempo") for t in sim.tiempos], "tiempo"))

    return f"""
<style>
.gantt-wrap {{ overflow-x: auto; }}
.gantt {{ border-collapse: collapse; font-size: 12px; font-family: ui-monospace, monospace; }}
.gantt th, .gantt td {{ border: 1px solid rgba(128,128,128,.4); padding: 3px 5px;
  text-align: center; min-width: 38px; white-space: nowrap; }}
.gantt th {{ text-align: left; min-width: 100px; }}
.gantt tr.titulo th {{ font-weight: 700; }}
.gantt td.ejec {{ font-weight: 700; }}
.gantt td.so {{ font-weight: 600; }}
.gantt tr.tiempo td, .gantt tr.tiempo th {{ opacity: .75; }}
</style>
<div class="gantt-wrap"><table class="gantt">{"".join(filas)}</table></div>
"""


def resumen_final(sim):
    df = calcular_metricas(sim)
    st.dataframe(df, hide_index=True, width="stretch")
    terminados = df.dropna(subset=["Retorno (q)"])
    c1, c2 = st.columns(2)
    if not terminados.empty:
        c1.metric("Retorno promedio", f"{terminados['Retorno (q)'].mean():.2f} q")
        c2.metric("Espera promedio", f"{terminados['Espera (q)'].mean():.2f} q")
    sin_terminar = df[df["Retorno (q)"].isna()]["Proceso"].tolist()
    if sin_terminar:
        st.warning(f"No terminaron dentro de {sim.tiempo_max} ut (excluidos del promedio): "
                   f"{', '.join(sin_terminar)}. Aumentá el tiempo máximo.")
    st.caption("q = quantum = 1 casilla de 10 ut. Retorno = fin − llegada. Espera = casillas en Listo.")


EJEMPLO = pd.DataFrame([
    {"ID": "p1", "Llegada (ut)": 10, "Ráfagas CPU (ut)": "30, 20"},
    {"ID": "p2", "Llegada (ut)": 20, "Ráfagas CPU (ut)": "10, 20, 10"},
    {"ID": "p3", "Llegada (ut)": 50, "Ráfagas CPU (ut)": "20, 30"},
])


def main():
    st.set_page_config(page_title="Planificación de CPU", layout="wide")
    st.title("Simulador de planificación de CPU")

    with st.sidebar:
        st.header("Parámetros")
        algoritmo = st.radio("Algoritmo", list(cargar_algoritmos().keys()))
        duracion_es = st.number_input("Duración de cada E/S (ut)", min_value=10, step=10, value=20)
        tiempo_max = st.number_input("Tiempo máximo (ut)", min_value=50, step=10, value=380)
        st.caption("1 casilla = 10 ut. Los valores deben ser múltiplos de 10.")
        st.subheader("Round Robin")
        quantum_auto = st.checkbox("Quantum automático (regla del 80%)", value=True,
                                   help="El quantum alcanza para que el 80% de las ráfagas de CPU "
                                        "terminen sin ser desalojadas.")
        quantum_manual = st.number_input("Quantum manual (ut)", min_value=10, step=10, value=30,
                                         disabled=quantum_auto)
        aviso_quantum = st.empty()

    no_multiplos = [nombre for nombre, valor in [("Duración de E/S", duracion_es),
                                                 ("Tiempo máximo", tiempo_max),
                                                 ("Quantum manual", quantum_manual)]
                    if valor % INTERVALO != 0]
    if no_multiplos:
        st.error(f"Deben ser múltiplos de {INTERVALO}: {', '.join(no_multiplos)}.")
        st.stop()

    st.subheader("Procesos")
    st.caption("Ráfagas de CPU separadas por coma; entre ráfaga y ráfaga el proceso hace una E/S.")
    df = st.data_editor(EJEMPLO, num_rows="dynamic", hide_index=True, width="stretch", key="procesos")

    filas, errores = parsear_procesos(df.dropna(how="all"))
    for e in errores:
        st.error(e)
    if errores or not filas:
        st.stop()

    if quantum_auto:
        quantum, cubiertas, total = quantum_regla_80(filas)
        aviso_quantum.info(f"Quantum = {quantum} ut: {cubiertas} de {total} ráfagas "
                           f"({cubiertas / total:.0%}) entran en un solo quantum.")
    else:
        quantum = quantum_manual
        cubiertas = sum(1 for f in filas for r in f["rafagas"] if r <= quantum)
        total = sum(len(f["rafagas"]) for f in filas)
        if cubiertas / total < 0.8:
            aviso_quantum.warning(f"Solo {cubiertas} de {total} ráfagas ({cubiertas / total:.0%}) "
                                  f"entran en {quantum} ut; la regla pide al menos 80%.")

    tab_gantt, tab_resumen, tab_comparar = st.tabs(["Diagrama de Gantt", "Resumen final", "Comparar algoritmos"])
    sim = simular(algoritmo, filas, duracion_es, quantum, tiempo_max)

    with tab_gantt:
        titulo = algoritmo + (f" (quantum = {quantum} ut)" if algoritmo == "Round Robin" else "")
        st.markdown(f"**{titulo}**")
        st.html(cuadro_html(sim))
        st.caption("Códigos S.O.: 1 carga · 2 a ejecución · 3 bloqueo · 4 fin de E/S · "
                   "5 desalojo / fin de quantum · 6 terminar")

    with tab_resumen:
        st.markdown(f"**Resumen final — {algoritmo}**")
        resumen_final(sim)

    with tab_comparar:
        filas_comp = []
        for nombre in cargar_algoritmos():
            m = calcular_metricas(simular(nombre, filas, duracion_es, quantum, tiempo_max))
            terminados = m.dropna(subset=["Retorno (q)"])
            filas_comp.append({
                "Algoritmo": nombre,
                "Retorno promedio (q)": round(terminados["Retorno (q)"].mean(), 2) if not terminados.empty else None,
                "Espera promedio (q)": round(terminados["Espera (q)"].mean(), 2) if not terminados.empty else None,
                "Sin terminar": len(m) - len(terminados),
            })
        st.dataframe(pd.DataFrame(filas_comp), hide_index=True, width="stretch")
        st.caption(f"Mismos procesos para los 4. Round Robin con quantum = {quantum} ut.")


if __name__ == "__main__":
    main()

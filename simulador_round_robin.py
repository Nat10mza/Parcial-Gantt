class Proceso:
    def __init__(self, id_proc, llegada, rafagas_cpu):
        self.id = id_proc.lower()
        self.llegada = llegada
        self.rafagas_cpu = rafagas_cpu  # Lista con los tiempos de cada ráfaga de CPU
        self.rafaga_idx = 0
        self.cpu_restante = rafagas_cpu[0] if rafagas_cpu else 0
        self.estado = "No llegado"
        self.estado_visual = "No llegado"


class SimuladorOSRoundRobin:
    def __init__(self, procesos, duracion_es_global, quantum, tiempo_max=480, intervalo=10):
        self.procesos = {p.id: p for p in procesos}
        self.duracion_es_global = duracion_es_global
        self.quantum = quantum
        self.tiempo_max = tiempo_max
        self.intervalo = intervalo
        self.tiempos = list(range(intervalo, tiempo_max + intervalo, intervalo))

        self.cola_listos = []
        self.cola_bloqueados = []  # {'proceso': p, 'tiempo_restante': x}
        self.ejecutando = None
        self.quantum_restante = 0  # Quantum que le queda al proceso en CPU

        self.eventos_so = {t: "" for t in self.tiempos}
        self.matriz_ejecutando = {t: "" for t in self.tiempos}
        self.matriz_terminado = {t: "" for t in self.tiempos}
        self.snapshots = {t: {} for t in self.tiempos}
        self.terminados = []  # [(tiempo_visual, id)] en orden de terminación

    def ejecutar(self):
        pendientes_visuales = {}  # {t_futuro: {p_id: nuevo_estado_visual}}

        for t in self.tiempos:
            # 1. Cambios visuales programados para este tick (retraso de 1 casilla)
            if t in pendientes_visuales:
                for p_id, est in pendientes_visuales[t].items():
                    self.procesos[p_id].estado_visual = est

            # 2. El tiempo transcurre para los procesos bloqueados (E/S)
            desbloqueados_ahora = []
            for item in self.cola_bloqueados:
                item['tiempo_restante'] -= self.intervalo
                if item['tiempo_restante'] <= 0:
                    desbloqueados_ahora.append(item['proceso'])

            # La CPU está "ocupada" si hay un proceso en medio de su ráfaga
            # y todavía le queda quantum. Mientras esté ocupada, el S.O. NO
            # puede interrumpirla con rutinas de carga ni de desbloqueo.
            cpu_ocupada = (self.ejecutando is not None
                           and self.ejecutando.cpu_restante > 0
                           and self.quantum_restante > 0)

            # 3. Única rutina del S.O. para este tick (por prioridad estricta)
            candidatos = []

            # Prioridad 2: Carga (rutina 1) - solo si la CPU no está en medio de una ráfaga
            if not cpu_ocupada:
                cargables = [p for p in self.procesos.values()
                             if p.estado == "No llegado" and p.llegada <= t]
                cargables.sort(key=lambda x: x.llegada)
                if cargables:
                    p_c = cargables[0]
                    candidatos.append((2, f"1{p_c.id.upper()}", "carga", p_c))

            # Prioridad 1: Terminar (6), Bloquear (3) o Fin de quantum (5)
            if self.ejecutando is not None:
                p_ex = self.ejecutando
                if p_ex.cpu_restante <= 0:
                    is_last = (p_ex.rafaga_idx >= len(p_ex.rafagas_cpu) - 1)
                    if is_last:
                        candidatos.append((1, f"6{p_ex.id.upper()}", "terminar", p_ex))
                    else:
                        candidatos.append((1, f"3{p_ex.id.upper()}", "bloquear", p_ex))
                elif self.quantum_restante <= 0:
                    # La ráfaga no terminó pero se agotó el quantum
                    candidatos.append((1, f"5{p_ex.id.upper()}", "timeout", p_ex))

            # Prioridad 3: Salida a Ejecución (rutina 2) - CPU libre y cola con listos
            if self.ejecutando is None and self.cola_listos:
                p_e = self.cola_listos[0]
                candidatos.append((3, f"2{p_e.id.upper()}", "ejecucion", p_e))

            # Prioridad 4: Regreso a Listo (rutina 4) - E/S terminada,
            # solo si la CPU no está en medio de una ráfaga
            if desbloqueados_ahora and not cpu_ocupada:
                p_d = desbloqueados_ahora[0]
                candidatos.append((4, f"4{p_d.id.upper()}", "desbloqueo", p_d))

            tipo_ejecutado = None
            proc_afectado = None
            if candidatos:
                candidatos.sort(key=lambda x: x[0])
                _, codigo, tipo, proc = candidatos[0]
                self.eventos_so[t] = codigo
                tipo_ejecutado = tipo
                proc_afectado = proc

            t_sig = t + self.intervalo
            if t_sig not in pendientes_visuales:
                pendientes_visuales[t_sig] = {}

            # Efectos de la rutina del S.O.
            if tipo_ejecutado == "carga":
                proc_afectado.estado = "Listo"
                proc_afectado.estado_visual = "No llegado"
                pendientes_visuales[t_sig][proc_afectado.id] = "Listo"
                self.cola_listos.append(proc_afectado)

            elif tipo_ejecutado == "terminar":
                p = self.ejecutando
                p.estado = "Terminado"
                p.estado_visual = "Ejecutando"
                pendientes_visuales[t_sig][p.id] = "Terminado"
                self.terminados.append((t_sig, p.id.upper()))
                self.ejecutando = None

            elif tipo_ejecutado == "bloquear":
                p = self.ejecutando
                p.estado = "Bloqueado"
                p.estado_visual = "Ejecutando"
                pendientes_visuales[t_sig][p.id] = "Bloqueado"
                self.cola_bloqueados.append({'proceso': p, 'tiempo_restante': self.duracion_es_global})
                self.ejecutando = None

            elif tipo_ejecutado == "timeout":
                # Rutina 5: Ejecutando -> Listo (va al final de la cola)
                p = self.ejecutando
                p.estado = "Listo"
                p.estado_visual = "Ejecutando"
                pendientes_visuales[t_sig][p.id] = "Listo"
                self.cola_listos.append(p)
                self.ejecutando = None

            elif tipo_ejecutado == "desbloqueo":
                self.cola_bloqueados = [i for i in self.cola_bloqueados if i['proceso'] != proc_afectado]
                proc_afectado.estado = "Listo"
                proc_afectado.estado_visual = "Bloqueado"
                pendientes_visuales[t_sig][proc_afectado.id] = "Listo"
                self.cola_listos.append(proc_afectado)
                proc_afectado.rafaga_idx += 1
                proc_afectado.cpu_restante = proc_afectado.rafagas_cpu[proc_afectado.rafaga_idx]

            elif tipo_ejecutado == "ejecucion":
                p = self.cola_listos.pop(0)
                p.estado = "Ejecutando"
                p.estado_visual = "Listo"
                pendientes_visuales[t_sig][p.id] = "Ejecutando"
                self.ejecutando = p
                self.quantum_restante = self.quantum  # Se asigna un quantum nuevo

            # 4. Procesamiento de CPU (excluyente con el S.O.)
            if self.ejecutando is not None and not self.eventos_so[t]:
                self.matriz_ejecutando[t] = self.ejecutando.id.upper()
                if self.ejecutando.estado_visual == "Ejecutando":
                    self.ejecutando.cpu_restante -= self.intervalo
                    self.quantum_restante -= self.intervalo

            # Snapshot del estado visual de todos los procesos en este tick
            for p_id, p in self.procesos.items():
                self.snapshots[t][p_id] = p.estado_visual

        # Fila "Terminado" ACUMULATIVA (una vez terminado, el proceso queda listado)
        for t in self.tiempos:
            ids = [pid for (tv, pid) in self.terminados if tv <= t]
            self.matriz_terminado[t] = ",".join(ids)

    def imprimir_cuadro(self):
        ids_procesos = sorted(list(self.procesos.keys()), reverse=True)  # p4 arriba, p1 abajo
        col_w = 9      # alcanza para "P1,P3,P4"
        label_w = 14
        tam_bloque = 10
        bloques = [self.tiempos[i:i + tam_bloque] for i in range(0, len(self.tiempos), tam_bloque)]

        print("\n" + "=" * 35 + f" SIMULACIÓN DE PLANIFICACIÓN ROUND ROBIN (QUANTUM = {self.quantum}) " + "=" * 35)

        for idx_bloque, tiempos_chunk in enumerate(bloques, 1):
            print(f"\n[ PARTE {idx_bloque} — Tiempos del {tiempos_chunk[0]} al {tiempos_chunk[-1]} ]")

            def linea_horizontal(tipo="mid"):
                if tipo == "top":
                    return "┌" + "─" * label_w + "┬" + "┬".join(["─" * col_w for _ in tiempos_chunk]) + "┐"
                elif tipo == "bot":
                    return "└" + "─" * label_w + "┴" + "┴".join(["─" * col_w for _ in tiempos_chunk]) + "┘"
                return "├" + "─" * label_w + "┼" + "┼".join(["─" * col_w for _ in tiempos_chunk]) + "┤"

            print(linea_horizontal("top"))

            term_vals = [f"{self.matriz_terminado[t]:^{col_w}}" for t in tiempos_chunk]
            print(f"│ {'Terminado':<{label_w-1}}│" + "│".join(term_vals) + "│")
            print(linea_horizontal())

            print(f"│ {'Bloqueado':<{label_w-1}}│" + "".join([" " * col_w + "│" for _ in tiempos_chunk]))
            for p_id in ids_procesos:
                row_vals = []
                for t in tiempos_chunk:
                    val = "x" if self.snapshots.get(t, {}).get(p_id, "") == "Bloqueado" else ""
                    row_vals.append(f"{val:^{col_w}}")
                print(f"│   {p_id.upper():<{label_w-3}}│" + "│".join(row_vals) + "│")
            print(linea_horizontal())

            ejec_vals = [f"{self.matriz_ejecutando[t]:^{col_w}}" for t in tiempos_chunk]
            print(f"│ {'Ejecutando':<{label_w-1}}│" + "│".join(ejec_vals) + "│")
            print(linea_horizontal())

            print(f"│ {'Listo':<{label_w-1}}│" + "".join([" " * col_w + "│" for _ in tiempos_chunk]))
            for p_id in ids_procesos:
                row_vals = []
                for t in tiempos_chunk:
                    val = "x" if self.snapshots.get(t, {}).get(p_id, "") == "Listo" else ""
                    row_vals.append(f"{val:^{col_w}}")
                print(f"│   {p_id.upper():<{label_w-3}}│" + "│".join(row_vals) + "│")
            print(linea_horizontal())

            so_vals = [f"{self.eventos_so[t]:^{col_w}}" for t in tiempos_chunk]
            print(f"│ {'S. Operativo':<{label_w-1}}│" + "│".join(so_vals) + "│")
            print(linea_horizontal())

            tiempo_vals = [f"{t:^{col_w}}" for t in tiempos_chunk]
            print(f"│ {'Tiempo':<{label_w-1}}│" + "│".join(tiempo_vals) + "│")
            print(linea_horizontal("bot"))

        print("=" * 100)


def solicitar_datos_usuario(intervalo=10):
    print("=== CONFIGURACIÓN DE PROCESOS PARA PLANIFICACIÓN ROUND ROBIN ===")

    while True:
        try:
            duracion_es_global = int(input("Ingrese el tiempo de duración en general para TODAS las E/S (ej. 90): "))
            break
        except ValueError:
            print("[Error] Por favor, ingresa un número entero válido.")

    while True:
        try:
            quantum = int(input(f"Ingrese el QUANTUM de tiempo (múltiplo de {intervalo}, ej. 30): "))
            if quantum <= 0:
                print("[Error] El quantum debe ser mayor que 0.")
                continue
            if quantum % intervalo != 0:
                ajustado = ((quantum // intervalo) + 1) * intervalo
                print(f"[Aviso] El quantum se ajustó de {quantum} a {ajustado} (múltiplo de {intervalo}).")
                quantum = ajustado
            break
        except ValueError:
            print("[Error] Por favor, ingresa un número entero válido.")

    while True:
        try:
            num_procesos = int(input("¿Cuántos procesos vas a ingresar? (Ej. 4): "))
            break
        except ValueError:
            print("[Error] Por favor, ingresa un número válido.")

    lista_procesos = []

    for i in range(1, num_procesos + 1):
        print(f"\n--- Configuración del Proceso {i} ---")
        id_proc = input("ID del proceso (ej. p1, p2): ").strip().lower()
        if not id_proc:
            id_proc = f"p{i}"

        while True:
            try:
                tiempo_llegada = int(input(f"Unidad de tiempo en la que ingresa {id_proc.upper()} (ej. 10, 20, 100, 190): "))
                break
            except ValueError:
                print("[Error] Ingresa un número entero válido para el tiempo de llegada.")

        rafagas_cpu = []
        print(f"Define las ráfagas de CPU de {id_proc.upper()}.")
        while True:
            try:
                num_cpu = int(input(f"¿Cuántas ráfagas de CPU tendrá {id_proc.upper()}? (Ej. 2 o 3): "))
                break
            except ValueError:
                print("[Error] Por favor, ingresa un número válido.")

        for c in range(1, num_cpu + 1):
            while True:
                try:
                    dur_cpu = int(input(f"  -> Duración de la ráfaga de CPU #{c}: "))
                    break
                except ValueError:
                    print("[Error] Por favor, ingresa un número válido.")
            rafagas_cpu.append(dur_cpu)

        lista_procesos.append(Proceso(id_proc, tiempo_llegada, rafagas_cpu))

    return lista_procesos, duracion_es_global, quantum


if __name__ == "__main__":
    try:
        procesos_usuario, duracion_es, quantum = solicitar_datos_usuario()
        print("\n[Procesando simulación, por favor espera...]")
        simulador = SimuladorOSRoundRobin(procesos_usuario, duracion_es, quantum, tiempo_max=480, intervalo=10)
        simulador.ejecutar()
        simulador.imprimir_cuadro()
    except Exception as e:
        print(f"\n[ERROR] Ocurrió un error inesperado: {e}")

    input("\nPresiona ENTER para salir del programa...")

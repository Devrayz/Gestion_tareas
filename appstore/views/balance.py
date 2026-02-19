import streamlit as st
import pandas as pd
import logic
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==============================================================================
# 1. LÓGICA: CÁLCULO QUIRÚRGICO (Basado en Transiciones)
# ==============================================================================
def calcular_esencia(fecha_inicio, fecha_fin):
    # Estados "Buenos" (Meta)
    estados_ok = ('OK', 'POSTVENTA CORREGIDA', 'TERMINADO', 'NO TIENE POSTVENTA', 'CERRADO', 'SIN NOVEDAD', 'ENTREGADO', 'RECIBIDO CONFORME')
    
    # 1. INGRESOS REALES (Nacieron Rotos)
    # Contamos tareas creadas en el rango que NO nacieron OK
    q_nuevos = """
        SELECT COUNT(*) as t FROM obras_tarea 
        WHERE created_at::date BETWEEN %s AND %s 
        AND estado NOT IN %s 
        AND es_postventa = TRUE
    """
    nuevos = logic.db.run_query(q_nuevos, (fecha_inicio, fecha_fin, estados_ok), return_data=True).iloc[0]['t']

    # 2. SOLUCIONES REALES (Estaban Rotos -> Se Arreglaron)
    # Aquí está el filtro de oro: Miramos el HISTORIAL.
    # Solo contamos si ANTES NO era OK y AHORA SI es OK.
    # Excluimos 'NUEVO' y 'CARGA_MAESTRA' para no contar los que nacieron bien.
    q_soluciones = """
        SELECT COUNT(DISTINCT tarea_id) as t 
        FROM obras_historial 
        WHERE fecha_cambio::date BETWEEN %s AND %s
        AND estado_anterior NOT IN %s -- Antes estaba Mal
        AND estado_anterior NOT IN ('NUEVO', 'CARGA_MAESTRA') -- Y no es un nacimiento
        AND estado_nuevo IN %s -- Ahora está Bien
    """
    soluciones = logic.db.run_query(q_soluciones, (fecha_inicio, fecha_fin, estados_ok, estados_ok), return_data=True).iloc[0]['t']

    # 3. RECAÍDAS (Estaban Bien -> Se Rompieron)
    q_recaidas = """
        SELECT COUNT(DISTINCT tarea_id) as t 
        FROM obras_historial 
        WHERE fecha_cambio::date BETWEEN %s AND %s
        AND estado_anterior IN %s -- Antes estaba Bien
        AND estado_nuevo NOT IN %s -- Ahora está Mal
    """
    recaidas = logic.db.run_query(q_recaidas, (fecha_inicio, fecha_fin, estados_ok, estados_ok), return_data=True).iloc[0]['t']

    # 4. SALDO NETO (Matemática simple)
    # (Lo que entró malo + Lo que se dañó) - (Lo que arreglamos)
    neto = (nuevos + recaidas) - soluciones
    
    # 5. INVENTARIO ACTIVO AHORA (La foto del momento)
    # Cuántos pendientes reales hay HOY en total
    q_pendientes_hoy = """
        SELECT COUNT(*) as t FROM obras_tarea 
        WHERE estado NOT IN %s AND es_postventa = TRUE
    """
    pendientes_hoy = logic.db.run_query(q_pendientes_hoy, (estados_ok,), return_data=True).iloc[0]['t']

    return {
        "nuevos": nuevos,
        "soluciones": soluciones,
        "recaidas": recaidas,
        "neto": neto,
        "pendientes_hoy": pendientes_hoy
    }

# ==============================================================================
# 2. VISTA VISUAL
# ==============================================================================
def mostrar_balance():
    st.subheader("🔍 La Esencia: Gestión de Pendientes")
    st.caption("Filtra el ruido y muestra solo el trabajo real sobre fallas.")

    # Filtros (Por defecto: Últimos 3 días para ver la gestión reciente)
    c1, c2 = st.columns(2)
    with c1: f_inicio = st.date_input("Desde", datetime.now() - timedelta(days=3))
    with c2: f_fin = st.date_input("Hasta", datetime.now())

    if f_inicio > f_fin:
        st.error("Fechas inválidas.")
        return

    try:
        data = calcular_esencia(f_inicio, f_fin)
        
        # --- TARJETAS GRANDES ---
        # Usamos colores para contar la historia
        
        k1, k2, k3, k4 = st.columns(4)
        
        # 1. Lo Malo (Entradas)
        k1.metric("🚨 Nuevas Fallas", f"+{data['nuevos']}", help="Items que nacieron con problemas")
        
        # 2. Lo Feo (Recaídas)
        k2.metric("🔙 Garantías", f"+{data['recaidas']}", delta_color="inverse", help="Estaban OK y fallaron")
        
        # 3. Lo Bueno (Soluciones)
        k3.metric("✅ Reparados", f"-{data['soluciones']}", delta_color="normal", help="Problemas reales que se solucionaron")
        
        # 4. El Veredicto (Neto)
        neto = data['neto']
        if neto < 0:
            lbl = "👏 Bajamos la Cola"
            clr = "normal" # Verde
            val = f"⬇ {abs(neto)}"
        elif neto > 0:
            lbl = "⚠️ Subió la Cola"
            clr = "inverse" # Rojo
            val = f"⬆ {neto}"
        else:
            lbl = "⚖️ Tablas"
            clr = "off"
            val = "0"
            
        k4.metric("Balance Semanal", val, lbl, delta_color=clr)

        st.divider()

        # --- EXPLICACIÓN GRÁFICA ---
        # Mostramos cómo llegamos a los pendientes de hoy
        
        # Estimamos pendientes al inicio restando el flujo inverso
        # (Pendientes Hoy) - (Entradas) + (Salidas) = (Pendientes Inicio Aprox)
        pendientes_inicio = data['pendientes_hoy'] - data['nuevos'] - data['recaidas'] + data['soluciones']
        
        fig = go.Figure(go.Waterfall(
            name = "Gestión", orientation = "v",
            measure = ["absolute", "relative", "relative", "relative", "total"],
            x = ["Pendientes Inicio", "Nuevos (+)", "Garantías (+)", "Reparados (-)", "Pendientes Hoy"],
            textposition = "outside",
            text = [pendientes_inicio, f"+{data['nuevos']}", f"+{data['recaidas']}", f"-{data['soluciones']}", data['pendientes_hoy']],
            y = [pendientes_inicio, data['nuevos'], data['recaidas'], -data['soluciones'], 0],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
        ))

        fig.update_traces(
            increasing={"marker":{"color":"#E74C3C"}}, # Rojo (Sube carga)
            decreasing={"marker":{"color":"#2ECC71"}}, # Verde (Baja carga)
            totals={"marker":{"color":"#2E86C1"}}      # Azul (Inventario)
        )
        
        fig.update_layout(title="Flujo de Trabajo Real (Sin contar OKs históricos)", showlegend=False, height=450)
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error de cálculo: {e}")

# ==============================================================================
# 3. AGING (Igual que siempre)
# ==============================================================================
def mostrar_aging():
    st.subheader("⏳ Semáforo de Tiempo")
    # ... (Mismo código de Aging que ya tienes y funciona bien) ...
    # Si quieres te lo pego completo de nuevo, pero es el mismo.
    query = """
        SELECT t.id, c.nombre as casa, a.nombre as area, i.nombre as item, t.estado,
               t.created_at::date as fecha, CURRENT_DATE - t.created_at::date as dias
        FROM obras_tarea t
        JOIN casas_general c ON t.casa_id = c.id
        JOIN maestro_areas a ON t.area_id = a.id
        JOIN maestro_items i ON t.item_id = i.id
        WHERE t.estado NOT IN ('OK', 'TERMINADO', 'POSTVENTA CORREGIDA', 'NO TIENE POSTVENTA', 'CERRADO', 'SIN NOVEDAD', 'ENTREGADO')
        AND t.es_postventa = TRUE
        ORDER BY dias DESC
    """
    df = logic.db.run_query(query, return_data=True)
    
    if df.empty:
        st.success("Nada pendiente.")
        return

    def clasificar(d):
        if d <= 15: return "🟢 Normal"
        elif d <= 30: return "🟡 Alerta"
        else: return "🔴 Crítico"
    
    df['Urgencia'] = df['dias'].apply(clasificar)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("Críticos", len(df[df['Urgencia'].str.contains("Crítico")]))
    c2.metric("Alerta", len(df[df['Urgencia'].str.contains("Alerta")]))
    c3.metric("Normal", len(df[df['Urgencia'].str.contains("Normal")]))
    
    g1, g2 = st.columns([1,2])
    with g1:
        fig = go.Figure(data=[go.Pie(labels=df['Urgencia'], values=df['id'], hole=.4)])
        fig.update_traces(marker=dict(colors=['#E74C3C', '#F1C40F', '#2ECC71'])) # Rojo, Amarillo, Verde
        st.plotly_chart(fig, use_container_width=True)
    with g2:
        st.dataframe(df[['casa', 'area', 'item', 'dias', 'Urgencia']], use_container_width=True)


def render_view():
    st.title("📊 Tablero de Control")
    t1, t2 = st.tabs(["📉 Balance", "⏳ Tiempos"])
    with t1: mostrar_balance()
    with t2: mostrar_aging()
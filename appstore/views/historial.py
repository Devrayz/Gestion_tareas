import streamlit as st
import pandas as pd
import plotly.express as px
import logic
from datetime import datetime, timedelta

def render_view():
    st.header("🕰️ Bitácora de Cambios y Avances")
    st.caption("Auditoría de movimientos: ¿Qué entró nuevo y qué se solucionó realmente?")

    # --- 1. FILTROS ---
    col_filters, col_actions = st.columns([2, 1])
    with col_filters:
        dias = st.slider("📅 Analizar historial de los últimos:", 1, 60, 7)
        fecha_corte = datetime.now() - timedelta(days=dias)
    
    with col_actions:
        # Botón de emergencia para limpiar duplicados viejos
        if st.button("🧹 Limpiar Duplicados Históricos"):
            try:
                logic.db.run_query("DELETE FROM obras_historial WHERE estado_anterior = estado_nuevo;")
                st.toast("Historial limpiado de redundancias.", icon="✨")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    # --- 2. CONSULTA ROBUSTA (Incluyendo Área e Item) ---
    query = """
        SELECT 
            h.fecha_cambio,
            c.nombre as casa,
            a.nombre as area,
            t.nombre as tarea,
            h.estado_anterior,
            h.estado_nuevo
        FROM obras_historial h
        JOIN obras_tarea t ON h.tarea_id = t.id
        JOIN casas_general c ON t.casa_id = c.id
        LEFT JOIN maestro_areas a ON t.area_id = a.id
        WHERE h.fecha_cambio >= %s
        ORDER BY h.fecha_cambio DESC
    """
    df_hist = logic.db.run_query(query, (fecha_corte,), return_data=True)

    if not df_hist.empty:
        # --- 3. PROCESAMIENTO INTELIGENTE DE METRICAS ---
        # Definimos qué es "Éxito"
        lista_ok = ['OK', 'TERMINADO', 'POSTVENTA CORREGIDA', 'CERRADO']
        
        # A. Cierres Reales: Pasó de NO-OK a SI-OK
        # Convertimos a mayúsculas para comparar seguro
        df_hist['nuevo_upper'] = df_hist['estado_nuevo'].str.upper().str.strip()
        df_hist['ant_upper'] = df_hist['estado_anterior'].str.upper().str.strip()

        cierres = df_hist[
            (df_hist['nuevo_upper'].isin(lista_ok)) & 
            (~df_hist['ant_upper'].isin(lista_ok))
        ]
        
        # B. Ingresos Nuevos: Vienen de 'NUEVO' o 'MIGRACION'
        ingresos = df_hist[df_hist['ant_upper'].isin(['NUEVO', 'MIGRACION'])]
        
        # C. Re-procesos: Estaba OK y volvió a fallar (Regresión)
        reprocesos = df_hist[
            (df_hist['ant_upper'].isin(lista_ok)) & 
            (~df_hist['nuevo_upper'].isin(lista_ok))
        ]

        # --- 4. VISUALIZACIÓN DE KPIs ---
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Movimientos", len(df_hist))
        k2.metric("📥 Nuevos Ingresos", len(ingresos), delta="Carga de Trabajo", delta_color="inverse")
        k3.metric("✅ Soluciones Reales", len(cierres), delta="Avance", delta_color="normal")
        k4.metric("⚠️ Regresiones", len(reprocesos), delta="Atención", delta_color="inverse")

        st.divider()

        # --- 5. GRÁFICAS DE ANÁLISIS ---
        g1, g2 = st.columns([2, 1])
        
        with g1:
            st.subheader("📊 Ritmo de Cierres Diarios")
            # Solo mostramos los cierres positivos en la gráfica para ver "Productividad"
            if not cierres.empty:
                cierres['fecha_dia'] = pd.to_datetime(cierres['fecha_cambio']).dt.date
                conteo_cierres = cierres.groupby(['fecha_dia', 'area']).size().reset_index(name='cantidad')
                
                fig = px.bar(
                    conteo_cierres, x='fecha_dia', y='cantidad', color='area',
                    title="Tickets Solucionados por Día y Área",
                    text_auto=True
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No hay cierres exitosos en este periodo.")

        with g2:
            st.subheader("📝 Últimos 10 Cambios")
            # Tabla limpia para lectura rápida
            df_show = df_hist[['fecha_cambio', 'casa', 'area', 'estado_anterior', 'estado_nuevo']].head(10)
            # Formato de fecha corto
            df_show['fecha_cambio'] = pd.to_datetime(df_show['fecha_cambio']).dt.strftime('%d/%m %H:%M')
            st.dataframe(df_show, hide_index=True, use_container_width=True)

    else:
        st.info(f"💤 No hay movimientos registrados en los últimos {dias} días.")
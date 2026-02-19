import streamlit as st
import pandas as pd
import logic
import plotly.express as px
from datetime import datetime

def render_view():
    st.header("📊 Dashboard de Gestión Postventa")

    # Inicialización
    df_tareas = pd.DataFrame() 
    
    try:
        # 1. LA GRAN CONSULTA (Traemos TODO para tener contexto)
        # Aquí pedimos el estado actual de los 6,000+ registros
        query = """
            SELECT t.estado, a.nombre as area, i.nombre as item, t.created_at, t.casa_id
            FROM obras_tarea t
            JOIN maestro_areas a ON t.area_id = a.id
            JOIN maestro_items i ON t.item_id = i.id
        """
        df_raw = logic.db.run_query(query, return_data=True)

        if df_raw is not None and not df_raw.empty:
            # 2. LIMPIEZA: Nos quedamos con la última foto de cada ítem
            df_raw['created_at'] = pd.to_datetime(df_raw['created_at'])
            df_raw = df_raw.sort_values('created_at', ascending=False)
            df_tareas = df_raw.drop_duplicates(subset=['casa_id', 'area', 'item'], keep='first')

            # 3. MÉTRICAS SUPERIORES
            lista_exito = ['OK', 'POSTVENTA CORREGIDA', 'TERMINADO', 'NO TIENE POSTVENTA', 'CERRADO', 'SIN NOVEDAD']
            
            total_total = len(df_tareas)
            listos = len(df_tareas[df_tareas['estado'].str.upper().str.strip().isin(lista_exito)])
            pendientes = total_total - listos

            c1, c2, c3 = st.columns(3)
            c1.metric("Total Ítems Obra", total_total)
            c2.metric("✅ Listos / OK", listos)
            c3.metric("⚠️ Con Postventa", pendientes, delta_color="inverse")

            st.divider()

            # 4. GRÁFICOS INTERMEDIOS (Manteniendo tu estilo)
            g1, g2 = st.columns(2)
            with g1:
                st.subheader("📍 Dónde están los Pendientes")
                # Solo para la torta, filtramos lo que NO está listo
                df_solo_malos = df_tareas[~df_tareas['estado'].str.upper().str.strip().isin(lista_exito)]
                if not df_solo_malos.empty:
                    conteo_area = df_solo_malos['area'].value_counts().reset_index()
                    fig1 = px.pie(conteo_area, values='count', names='area', hole=0.4)
                    st.plotly_chart(fig1, use_container_width=True)
                else:
                    st.success("No hay pendientes")

            with g2:
                st.subheader("🔧 Fallas más comunes")
                if not df_solo_malos.empty:
                    conteo_item = df_solo_malos['item'].value_counts().head(10).reset_index()
                    fig2 = px.bar(conteo_item, x='count', y='item', orientation='h', text='count')
                    st.plotly_chart(fig2, use_container_width=True)
                
            # ------------------------------------------------------------------
            # 5. GRÁFICA COMPARATIVA FINAL (AVANCE POR ÁREA)
            # ------------------------------------------------------------------
            st.subheader("📊 Avance de Calidad por Área")
            st.caption("Barra Verde: Ítems OK o Reparados | Barra Roja: Pendientes")
            
            # Clasificamos todo el universo de datos
            df_tareas['Resultado'] = df_tareas['estado'].apply(
                lambda x: '✅ Solucionado / OK' if str(x).strip().upper() in lista_exito else '⚠️ Pendiente'
            )
            
            # Agrupamos por área
            datos_grafico = df_tareas.groupby(['area', 'Resultado']).size().reset_index(name='cantidad')

            # Gráfica LADO A LADO
            fig_final = px.bar(
                datos_grafico, 
                x="area", 
                y="cantidad", 
                color="Resultado",
                barmode='group', # <--- Las pone juntas para comparar
                text_auto=True,
                color_discrete_map={
                    "✅ Solucionado / OK": "#2ECC71", # Verde
                    "⚠️ Pendiente": "#E74C3C"        # Rojo
                },
                height=500
            )
            
            fig_final.update_layout(
                xaxis_title="Áreas de la Obra",
                yaxis_title="Cantidad de Ítems",
                legend_title=None
            )
            
            st.plotly_chart(fig_final, use_container_width=True)

        else:
            st.info("Sin datos para analizar.")

    except Exception as e:
        st.error(f"Error: {e}")
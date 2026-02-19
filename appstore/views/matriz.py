import streamlit as st
import pandas as pd
import logic

def obtener_color_area(estado_agrupado):
    """
    Define el color del cuadrito según el resumen del área.
    Prioridad: ROJO > AMARILLO > VERDE
    """
    # Convertimos a string por seguridad
    texto = str(estado_agrupado).upper()
    
    if 'TIENE' in texto: # Si hay al menos una falla (TIENE POSTVENTA)
        return 'background-color: #ffcccc; color: transparent' # Rojo
    elif 'CORREGIDA' in texto:
        return 'background-color: #fff3cd; color: transparent' # Amarillo
    else:
        return 'background-color: #d4edda; color: transparent' # Verde

def render_view():
    st.header("🗺️ Mapa de Calor General")
    st.caption("Visualización compacta. Cada cuadro representa el estado general de un Área en una Casa.")
    
    # --- 1. LEYENDA ---
    c1, c2, c3 = st.columns(3)
    c1.markdown("🟥 **Rojo:** Hay pendientes activos")
    c2.markdown("🟨 **Amarillo:** Hubo fallas, ya corregidas")
    c3.markdown("🟩 **Verde:** Área entregada OK")

    st.divider()

    # --- 2. CONSULTA SQL (Alias en minúsculas) ---
    # Usamos alias simples: casa, area, resumen
    query = """
        SELECT 
            c.nombre as casa, 
            a.nombre as area,
            STRING_AGG(t.estado, ',') as resumen
        FROM obras_tarea t
        JOIN casas_general c ON t.casa_id = c.id
        JOIN maestro_areas a ON t.area_id = a.id
        GROUP BY c.id, c.nombre, a.id, a.nombre
        ORDER BY c.id, a.id
    """
    
    df_raw = logic.db.run_query(query, return_data=True)

    if df_raw is None or df_raw.empty:
        st.info("No hay datos suficientes para generar el mapa.")
        return

    # Normalizamos nombres de columnas (por si acaso la librería los trae diferente)
    df_raw.columns = df_raw.columns.str.lower()

    # --- 3. TRANSFORMACIÓN (Pivot) ---
    # Usamos las columnas en minúsculas: 'area', 'casa', 'resumen'
    df_pivot = df_raw.pivot_table(index='area', columns='casa', values='resumen', aggfunc='first')
    df_pivot = df_pivot.fillna("OK") 

    # --- 4. VISUALIZACIÓN ---
    st.markdown("""
        <style>
            .stDataFrame td {
                height: 30px !important;
                min-width: 30px !important;
                font-size: 0px !important; /* Oculta el texto */
                color: transparent !important;
            }
        </style>
    """, unsafe_allow_html=True)

    st.dataframe(
        df_pivot.style.applymap(obtener_color_area),
        use_container_width=True,
        height=700
    )

    # --- 5. DETALLE ---
    with st.expander("🔎 Ver detalle de un Área específica"):
        # Usamos df_pivot.index que ahora contiene las áreas
        area_selec = st.selectbox("Selecciona Área:", df_pivot.index)
        
        if area_selec:
            # Consulta de detalle
            q_detalle = f"""
                SELECT c.nombre as casa, i.nombre as item, t.estado
                FROM obras_tarea t
                JOIN casas_general c ON t.casa_id = c.id
                JOIN maestro_items i ON t.item_id = i.id
                JOIN maestro_areas a ON t.area_id = a.id
                WHERE a.nombre = '{area_selec}'
            """
            df_det = logic.db.run_query(q_detalle, return_data=True)
            if df_det is not None:
                # Normalizamos columnas del detalle también
                df_det.columns = df_det.columns.str.lower()
                piv_det = df_det.pivot_table(index='item', columns='casa', values='estado', aggfunc='first')
                st.write(f"**Detalle: {area_selec}**")
                st.dataframe(piv_det)
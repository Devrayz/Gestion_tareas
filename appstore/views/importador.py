import streamlit as st
import pandas as pd
import logic
import utils 
import time

def render_view():
    st.header("📥 Inyector Inteligente (Modo Diagnóstico)")
    st.caption("Carga masiva con reporte de errores si los nombres no coinciden.")
    
    if st.button("🔧 Liberar Restricciones (Si hay errores de BD)", key="btn_fix_smart"):
        logic.db.run_query("ALTER TABLE obras_tarea DROP CONSTRAINT IF EXISTS check_estados_validos;")
        st.success("✅ BD lista.")

    # --- 1. CARGA DE CATÁLOGOS ---
    df_casas_bd = logic.db.run_query("SELECT id, nombre FROM casas_general ORDER BY id", return_data=True)
    lista_casas = df_casas_bd['nombre'].tolist() if df_casas_bd is not None else []
    mapa_casas_selector = {nombre: id for nombre, id in zip(df_casas_bd['nombre'], df_casas_bd['id'])} if df_casas_bd is not None else {}

    # --- 2. INTERFAZ ---
    col_casa, col_file = st.columns([1, 2])
    
    with col_casa:
        casa_seleccionada = st.selectbox("🏠 Casa Destino", options=lista_casas)
        id_casa_global = mapa_casas_selector.get(casa_seleccionada)

    with col_file:
        uploaded_file = st.file_uploader("Sube el archivo importacion_CASA_XX.csv", type=["csv"], key="file_smart")

    # --- 3. SELECTOR DE RESPONSABLE ---
    id_responsable = None
    try:
        df_users = logic.db.run_query("SELECT id, email FROM auth.users", return_data=True) 
        if df_users is not None and not df_users.empty:
            opciones = {email: uid for email, uid in zip(df_users['email'], df_users['id'])}
            responsable = st.selectbox("Asignar Responsable", options=list(opciones.keys()))
            id_responsable = opciones[responsable]
    except:
        pass

    # --- 4. PROCESAMIENTO CON DIAGNÓSTICO ---
    if uploaded_file and st.button("🚀 Analizar e Inyectar", type="primary"):
        if not id_casa_global:
            st.error("⚠️ Selecciona una casa.")
            return

        df = pd.read_csv(uploaded_file, on_bad_lines='skip')
        st.write("👀 **Vista previa de lo que leyó el sistema:**")
        st.dataframe(df.head(3)) # Para ver si leyó bien las columnas

        # Cargar Mapas
        df_areas_bd = logic.db.run_query("SELECT id, nombre FROM maestro_areas", return_data=True)
        df_items_bd = logic.db.run_query("SELECT id, nombre FROM maestro_items", return_data=True)
        
        mapa_areas = {str(n).strip().upper(): id for n, id in zip(df_areas_bd['nombre'], df_areas_bd['id'])} if df_areas_bd is not None else {}
        mapa_items = {str(n).strip().upper(): id for n, id in zip(df_items_bd['nombre'], df_items_bd['id'])} if df_items_bd is not None else {}

        # Verificar BD actual
        existentes_bd = logic.db.run_query(f"SELECT id, casa_id, area_id, item_id, estado FROM obras_tarea WHERE casa_id = {id_casa_global}", return_data=True)
        dict_check = {}
        if existentes_bd is not None:
            for _, r in existentes_bd.iterrows():
                dict_check[(r['casa_id'], r['area_id'], r['item_id'])] = {'id': r['id'], 'estado': str(r['estado']).strip().upper()}

        # Contadores y LOG DE ERRORES
        nuevos, actualizados, sin_cambios = 0, 0, 0
        errores = [] # Aquí guardaremos por qué no carga

        progress_bar = st.progress(0)
        total_rows = len(df)

        for i, row in df.iterrows():
            # 1. Limpieza de nombres del CSV
            txt_area = utils.limpiar_texto(row.get('Area', '')).upper()
            txt_item = utils.limpiar_texto(row.get('Item', '')).upper()
            
            # 2. Búsqueda de IDs (El momento de la verdad)
            id_area = mapa_areas.get(txt_area)
            id_item = mapa_items.get(txt_item)

            # 3. Diagnóstico de fallos
            if not id_area:
                errores.append(f"Fila {i+1}: Área '{txt_area}' no existe en la BD.")
                continue # Salta a la siguiente
            
            if not id_item:
                errores.append(f"Fila {i+1}: Ítem '{txt_item}' no existe en la BD.")
                continue # Salta a la siguiente

            # 4. Si todo coincide, Inyectamos
            try:
                estado_csv = str(row.get('Estado', 'PENDIENTE')).strip().upper()
                descripcion_csv = str(row.get('Detalles', '')).strip()
                if not descripcion_csv and estado_csv == "OK": descripcion_csv = "Sin novedades"

                llave = (id_casa_global, id_area, id_item)
                
                if llave in dict_check:
                    # Actualizar
                    info = dict_check[llave]
                    if estado_csv != info['estado']:
                        logic.db.run_query("""
                            UPDATE obras_tarea SET estado=%s, descripcion=%s, responsable_id=%s, updated_at=NOW() WHERE id=%s
                        """, (estado_csv, descripcion_csv, id_responsable, info['id']))
                        logic.db.run_query("""
                            INSERT INTO obras_historial (tarea_id, estado_anterior, estado_nuevo, fecha_cambio) VALUES (%s, %s, %s, NOW())
                        """, (info['id'], info['estado'], estado_csv))
                        actualizados += 1
                    else:
                        sin_cambios += 1
                else:
                    # Nuevo
                    res = logic.db.run_query("""
                        INSERT INTO obras_tarea (casa_id, area_id, item_id, nombre, descripcion, estado, es_postventa, responsable_id, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, TRUE, %s, NOW()) RETURNING id
                    """, (id_casa_global, id_area, id_item, f"{txt_item} en {txt_area}", descripcion_csv, estado_csv, id_responsable), return_data=True)
                    if res is not None:
                        logic.db.run_query("""
                            INSERT INTO obras_historial (tarea_id, estado_anterior, estado_nuevo, fecha_cambio) VALUES (%s, 'NUEVO', %s, NOW())
                        """, (int(res.iloc[0]['id']), estado_csv))
                    nuevos += 1

            except Exception as e:
                errores.append(f"Fila {i+1}: Error de BD -> {e}")

            if i % 10 == 0: progress_bar.progress(min(1.0, (i + 1) / total_rows))

        progress_bar.progress(100)
        
        # --- REPORTE FINAL ---
        st.divider()
        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Nuevos", nuevos)
        c2.metric("🔄 Actualizados", actualizados)
        c3.metric("⚠️ Ignorados", len(errores))

        if errores:
            st.error("🚫 **Filas que no se pudieron cargar (Revisar nombres):**")
            st.write(errores) # Muestra la lista de culpas
        else:
            st.success("🎉 ¡Carga perfecta! Todos los datos entraron.")
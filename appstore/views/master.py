import streamlit as st
import pandas as pd
import logic
import utils
import re

def normalizar_nombre_casa(nombre):
    if pd.isna(nombre): return nombre
    match = re.search(r'#(\d+)', str(nombre))
    if match:
        num = int(match.group(1))
        return f"CASA #{num:02d}"
    return str(nombre).strip().upper()

def render_view():
    st.header("🚀 Importador Maestro: Actualización y Sincronización")
    st.info("Este proceso actualiza estados existentes y crea nuevos sin duplicar, incluyendo registros OK.")
    
    if st.button("🔧 Limpiar Restricciones", key="maestro_btn_fix"):
        logic.db.run_query("ALTER TABLE obras_tarea DROP CONSTRAINT IF EXISTS check_estados_validos;")
        st.success("✅ BD Lista para recibir cualquier estado.")

    col1, col2 = st.columns(2)
    f_gen = col1.file_uploader("1. Subir GENERAL.csv", type=["csv"])
    f_obs = col2.file_uploader("2. Subir OBSERVACIONES.csv", type=["csv"])

    if f_gen and f_obs:
        if st.button("⚡ Iniciar Sincronización Total", type="primary"):
            try:
                # 1. LECTURA CON PRESERVACIÓN DE ÁREAS
                # El header 3 es donde empiezan los nombres de las casas en el General
                df_gen = pd.read_csv(f_gen, sep=';', header=3, encoding='latin1')
                df_obs = pd.read_csv(f_obs, sep=';', header=1, encoding='latin1')

                # Renombramos la primera columna (que viene como Unnamed: 0) a 'AREA'
                df_gen.rename(columns={df_gen.columns[0]: 'AREA'}, inplace=True)
                df_obs.rename(columns={df_obs.columns[0]: 'AREA'}, inplace=True)

                # Rellenamos las áreas hacia abajo (ffill)
                df_gen['AREA'] = df_gen['AREA'].ffill()
                df_obs['AREA'] = df_obs['AREA'].ffill()

                # --- FASE 2: SINCRONIZACIÓN DE CATÁLOGOS (Áreas e Ítems) ---
                status = st.empty()
                status.info("🛠️ Sincronizando catálogos...")

                # A. Ítems
                df_items_bd = logic.db.run_query("SELECT id, nombre FROM maestro_items", return_data=True)
                mapa_items = {str(n).strip().upper(): id for n, id in zip(df_items_bd['nombre'], df_items_bd['id'])}
                
                # B. Áreas
                df_areas_bd = logic.db.run_query("SELECT id, nombre FROM maestro_areas", return_data=True)
                mapa_areas = {str(n).strip().upper(): id for n, id in zip(df_areas_bd['nombre'], df_areas_bd['id'])}

                # --- FASE 3: APLANADO (MELT) ---
                cols_casa_gen = [c for c in df_gen.columns if "CASA #" in str(c).upper()]
                cols_casa_obs = [c for c in df_obs.columns if "CASA #" in str(c).upper()]

                # Aplanamos para tener una fila por cada tarea
                gen_flat = df_gen.melt(id_vars=['AREA', 'DETALLES'], value_vars=cols_casa_gen, var_name='CASA', value_name='ESTADO')
                obs_flat = df_obs.melt(id_vars=['AREA', 'DETALLES'], value_vars=cols_casa_obs, var_name='CASA', value_name='OBS')

                gen_flat['CASA_NORM'] = gen_flat['CASA'].apply(normalizar_nombre_casa)
                obs_flat['CASA_NORM'] = obs_flat['CASA'].apply(normalizar_nombre_casa)

                # Cruzamos General con Observaciones
                df_final = pd.merge(gen_flat, obs_flat[['AREA', 'DETALLES', 'CASA_NORM', 'OBS']], 
                                    on=['AREA', 'DETALLES', 'CASA_NORM'], how='inner')
                
                # Limpieza de Estados: Todo a MAYÚSCULAS
                df_final['ESTADO'] = df_final['ESTADO'].fillna('SIN NOVEDAD').str.upper().str.strip()
                
                # --- FASE 4: GUARDADO CON UPSERT (No duplicados) ---
                # Mapeo de Casas
                casas_bd = logic.db.run_query("SELECT id, nombre FROM casas_general", return_data=True)
                mapa_casas = {utils.extraer_numero_casa(n): id for n, id in zip(casas_bd['nombre'], casas_bd['id'])}

                # Traemos lo existente para comparar en memoria (Velocidad)
                existentes = logic.db.run_query("SELECT id, casa_id, area_id, item_id, estado FROM obras_tarea", return_data=True)
                dict_check = {}
                if existentes is not None and not existentes.empty:
                    for _, r in existentes.iterrows():
                        dict_check[(r['casa_id'], r['area_id'], r['item_id'])] = {'id': r['id'], 'estado': str(r['estado']).upper()}

                pbar = st.progress(0)
                stats = {"nuevos": 0, "actualizados": 0, "iguales": 0}
                total = len(df_final)

                for idx, row in df_final.iterrows():
                    id_casa = mapa_casas.get(utils.extraer_numero_casa(row['CASA_NORM']))
                    id_area = mapa_areas.get(str(row['AREA']).strip().upper())
                    id_item = mapa_items.get(str(row['DETALLES']).strip().upper())

                    if id_casa and id_area and id_item:
                        key = (id_casa, id_area, id_item)
                        estado_nuevo = row['ESTADO']
                        detalle_obs = str(row['OBS'])[:250] # Limitar longitud

                        if key in dict_check:
                            # ACTUALIZAR SI CAMBIÓ
                            tarea_bd = dict_check[key]
                            if estado_nuevo != tarea_bd['estado']:
                                logic.db.run_query("""
                                    UPDATE obras_tarea SET estado = %s, descripcion = %s, updated_at = NOW() WHERE id = %s
                                """, (estado_nuevo, detalle_obs, tarea_bd['id']))
                                
                                logic.db.run_query("""
                                    INSERT INTO obras_historial (tarea_id, estado_anterior, estado_nuevo, fecha_cambio)
                                    VALUES (%s, %s, %s, NOW())
                                """, (tarea_bd['id'], tarea_bd['estado'], estado_nuevo))
                                stats["actualizados"] += 1
                            else:
                                stats["iguales"] += 1
                        else:
                            # INSERTAR NUEVO
                            res = logic.db.run_query("""
                                INSERT INTO obras_tarea (casa_id, area_id, item_id, nombre, descripcion, estado, es_postventa)
                                VALUES (%s, %s, %s, %s, %s, %s, TRUE) RETURNING id
                            """, (id_casa, id_area, id_item, row['DETALLES'], detalle_obs, estado_nuevo), return_data=True)
                            
                            if res is not None and not res.empty:
                                logic.db.run_query("""
                                    INSERT INTO obras_historial (tarea_id, estado_anterior, estado_nuevo, fecha_cambio)
                                    VALUES (%s, 'CARGA_MAESTRA', %s, NOW())
                                """, (int(res.iloc[0]['id']), estado_nuevo))
                            stats["nuevos"] += 1

                    pbar.progress((idx + 1) / total)

                st.success(f"🏁 Sincronización Completa")
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Nuevos", stats["nuevos"])
                col_b.metric("Actualizados", stats["actualizados"])
                col_c.metric("Sin Cambios", stats["iguales"])

            except Exception as e:
                st.error(f"❌ Error: {e}")
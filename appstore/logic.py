import streamlit as st
import psycopg2
import pandas as pd
import sys

# Esto ayuda si Pandas tiene que procesar tablas gigantes
sys.setrecursionlimit(2000)

class Database:
    def __init__(self):
        self.conn = None

    def _conectar(self):
        """
        En LOCALHOST: Busca el archivo .streamlit/secrets.toml
        En CLOUD: Busca los secrets del dashboard.
        Funciona igual en ambos lados.
        """
        try:
            if self.conn is None or self.conn.closed:
                # Conexión directa a PostgreSQL
                self.conn = psycopg2.connect(
                    host=st.secrets["postgres"]["host"],
                    user=st.secrets["postgres"]["user"],
                    password=st.secrets["postgres"]["password"],
                    dbname=st.secrets["postgres"]["dbname"],
                    port=st.secrets["postgres"]["port"]
                )
            return self.conn
        except FileNotFoundError:
            st.error("❌ No encuentro el archivo .streamlit/secrets.toml")
            st.stop()
        except Exception as e:
            st.error(f"🚨 Error conectando a Supabase: {e}")
            return None

    def run_query(self, query, params=None, return_data=False):
        conn = self._conectar()
        if not conn: return None

        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                
                if return_data: # Para SELECT
                    col_names = [desc[0] for desc in cur.description]
                    return pd.DataFrame(cur.fetchall(), columns=col_names)
                else: # Para INSERT / UPDATE
                    conn.commit()
                    return True
                    
        except Exception as e:
            conn.rollback()
            st.error(f"❌ Error SQL: {e}")
            return None


db = Database()



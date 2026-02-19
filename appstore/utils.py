import pandas as pd
from fpdf import FPDF
from datetime import datetime
import re

class ReportePro(FPDF):
    def header(self):
        # Barra superior oscura elegante
        self.set_fill_color(33, 37, 41)
        self.rect(0, 0, 210, 40, 'F')
        
        self.set_text_color(255, 255, 255)
        self.set_font('helvetica', 'B', 18)
        self.cell(0, 15, 'REPORTE EJECUTIVO DE POSTVENTA', 0, 1, 'C')
        
        self.set_font('helvetica', '', 10)
        fecha_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        self.cell(0, 5, f'Rayztech Cartagena | Corte de Información: {fecha_str}', 0, 1, 'C')
        self.ln(15)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f'Informe generado por Sistema Rayztech | Página {self.page_no()}', 0, 0, 'C')



def extraer_numero_casa(nombre):
    """
    Extrae el número de una cadena como 'CASA #05' y lo devuelve como entero (5).
    """
    if not nombre or pd.isna(nombre):
        return None
    # Busca el número que sigue al símbolo #
    match = re.search(r'#(\d+)', str(nombre))
    if match:
        return int(match.group(1))
    return None

def limpiar_texto(texto):
    """
    Recibe cualquier cosa (None, 'nan', texto sucio) y devuelve
    un string limpio en mayúsculas sin espacios extra.
    Ej: "  Baño   " -> "BAÑO"
    """
    if texto is None:
        return ""
    
    # Convertimos a string
    texto = str(texto).strip()
    
    # Manejo de valores nulos típicos de Pandas/Excel
    if texto.lower() in ['nan', 'none', 'nat', '']:
        return ""
        
    return texto

def extraer_numero_casa(texto_casa):
    """
    Intenta sacar el número de una cadena como 'CASA #14' o 'Casa 14'.
    Devuelve '14' o None si no encuentra números.
    """
    if not texto_casa:
        return None
        
    # Busca el primer grupo de dígitos en el texto
    match = re.search(r'\d+', str(texto_casa))
    if match:
        return match.group()
        
    return None


def generar_pdf(df_total, kpis):

    try:
        pdf = ReportePro()
        pdf.add_page()
        
        # --- SECCIÓN 1: DASHBOARD DE INDICADORES (Tres columnas) ---
        pdf.ln(10)
        y_inicial = pdf.get_y()
        
        # Caja 1: Pendientes (Rojo)
        pdf.set_fill_color(255, 235, 235) # Fondo suave
        pdf.rect(10, y_inicial, 60, 30, 'F')
        pdf.set_xy(10, y_inicial + 5)
        pdf.set_text_color(200, 0, 0)
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(60, 5, "POR CORREGIR", 0, 1, 'C')
        pdf.set_font('helvetica', 'B', 24)
        pdf.cell(60, 15, str(kpis['pendientes']), 0, 0, 'C')

        # Caja 2: Corregidas (Verde)
        pdf.set_fill_color(235, 255, 235)
        pdf.rect(75, y_inicial, 60, 30, 'F')
        pdf.set_xy(75, y_inicial + 5)
        pdf.set_text_color(0, 150, 0)
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(60, 5, "SOLUCIONADAS", 0, 1, 'C')
        pdf.set_font('helvetica', 'B', 24)
        pdf.cell(60, 15, str(kpis['terminados']), 0, 0, 'C')

        # Caja 3: Porcentaje (Azul)
        pdf.set_fill_color(235, 245, 255)
        pdf.rect(140, y_inicial, 60, 30, 'F')
        pdf.set_xy(140, y_inicial + 5)
        pdf.set_text_color(0, 100, 200)
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(60, 5, "% CUMPLIMIENTO", 0, 1, 'C')
        pdf.set_font('helvetica', 'B', 24)
        porcentaje = f"{kpis['porcentaje']}%"
        pdf.cell(60, 15, porcentaje, 0, 1, 'C')

        # --- SECCIÓN 2: BARRA DE PROGRESO VISUAL ---
        pdf.ln(15)
        pdf.set_xy(10, y_inicial + 35)
        pdf.set_text_color(50, 50, 50)
        pdf.set_font('helvetica', 'B', 11)
        pdf.cell(0, 10, "Avance Total del Proyecto:", 0, 1)
        
        # Dibujar barra
        pdf.set_fill_color(220, 220, 220) # Fondo gris
        pdf.rect(10, pdf.get_y(), 190, 6, 'F')
        
        pdf.set_fill_color(46, 204, 113) # Verde progreso
        ancho_verde = (kpis['porcentaje'] / 100) * 190
        pdf.rect(10, pdf.get_y(), ancho_verde, 6, 'F')
        pdf.ln(12)

        # --- SECCIÓN 3: TABLA DE PENDIENTES (Solo los 15 más urgentes) ---
        pdf.set_text_color(0, 0, 0)
        pdf.set_font('helvetica', 'B', 13)
        pdf.cell(0, 10, "DETALLE DE POSTVENTAS PENDIENTES (TOP 15)", 0, 1, 'L')
        
        # Encabezados de tabla
        pdf.set_fill_color(50, 50, 50)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font('helvetica', 'B', 10)
        pdf.cell(25, 10, "CASA", 1, 0, 'C', True)
        pdf.cell(115, 10, "ITEM / FALLA", 1, 0, 'C', True)
        pdf.cell(50, 10, "ESTADO", 1, 1, 'C', True)

        # Filtrado de datos: Solo lo que NO está terminado
        lista_ok = ['TERMINADO', 'POSTVENTA CORREGIDA', 'OK', 'NO TIENE POSTVENTA', 'CERRADO']
        df_pendientes = df_total[~df_total['estado'].str.upper().isin(lista_ok)].head(15)

        pdf.set_text_color(0, 0, 0)
        pdf.set_font('helvetica', '', 9)
        
        for _, row in df_pendientes.iterrows():
            pdf.cell(25, 8, f"#{row['casa_id']}", 1, 0, 'C')
            pdf.cell(115, 8, f" {str(row['item'])[:65]}", 1)
            # Resaltar estado en rojo
            pdf.set_text_color(200, 0, 0)
            pdf.cell(50, 8, str(row['estado']), 1, 1, 'C')
            pdf.set_text_color(0, 0, 0)

        return bytes(pdf.output())
    except Exception as e:
        print(f"Error PDF: {e}")
        return None
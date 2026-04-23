import os
import time
import random
import requests
import feedparser
import schedule
import google.generativeai as genai
from pypdf import PdfReader
from supabase import create_client, Client
from dotenv import load_dotenv

# 1. Cargar configuración y variables de entorno
load_dotenv()

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
ai_model = genai.GenerativeModel('gemini-1.5-flash')

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CV_FILE = os.getenv("NOMBRE_CV", "CV.pdf")

# Inicializar cliente de Base de Datos
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FUNCIONES DE EXTRACCIÓN Y ANÁLISIS ---

def extraer_texto_cv():
    """Lee el contenido del archivo PDF configurado."""
    try:
        reader = PdfReader(CV_FILE)
        texto = ""
        for page in reader.pages:
            texto += page.extract_text()
        return texto
    except Exception as e:
        print(f"❌ Error crítico: No se pudo leer {CV_FILE}. Asegúrate de que el archivo esté en la carpeta.")
        return None

def analizar_con_ia(cv_texto, titulo_empleo, descripcion_empleo):
    """Usa Google Gemini para decidir si la oferta encaja con tu perfil."""
    prompt = f"""
    Actúa como un experto en selección de personal (Headhunter). 
    Analiza si el siguiente CV encaja con la oferta de trabajo proporcionada.
    
    [CV DEL CANDIDATO]
    {cv_texto}
    
    [OFERTA DE TRABAJO]
    Título: {titulo_empleo}
    Descripción: {descripcion_empleo}
    
    RESPUESTA REQUERIDA (Formato Estricto):
    MATCH: [SI o NO]
    PUNTAJE: [0-100]
    RAZÓN: [Máximo 2 frases de por qué encaja]
    PROPUESTA: [Un mensaje corto y profesional para aplicar a este puesto]
    """
    try:
        response = ai_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"⚠️ Error en la IA: {e}")
        return "MATCH: NO"

# --- FUNCIONES DE COMUNICACIÓN ---

def enviar_telegram(mensaje):
    """Envía la notificación al chat de Telegram configurado."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": mensaje, 
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"⚠️ No se pudo enviar mensaje a Telegram: {e}")

def ya_notificado(job_id):
    """Verifica en Supabase si ya te enviamos esta oferta antes."""
    try:
        res = supabase.table("jobs_notified").select("job_id").eq("job_id", job_id).execute()
        return len(res.data) > 0
    except Exception as e:
        print(f"⚠️ Error consultando DB: {e}")
        return False

def registrar_job(job_id):
    """Guarda el link de la oferta para no repetirla."""
    try:
        supabase.table("jobs_notified").insert({"job_id": job_id}).execute()
    except Exception as e:
        print(f"⚠️ Error guardando en DB: {e}")

# --- TAREA PRINCIPAL ---

def ejecutar_escaneo():
    print(f"\n🕒 [{time.strftime('%H:%M:%S')}] Iniciando escaneo de vacantes...")
    
    cv_texto = extraer_texto_cv()
    if not cv_texto:
        return

    fuentes = [
        {"nombre": "Forobeta", "url": "https://forobeta.com/forums/ofertas-de-trabajo/index.rss"},
        {"nombre": "We Work Remotely", "url": "https://weworkremotely.com/remote-jobs.rss"},
        {"nombre": "Get on Board", "url": "https://www.getonbrd.com/jobs/remote.rss"},
        {"nombre": "RemoteOK", "url": "https://remoteok.com/remote-jobs.rss"}
    ]

    encontrados = 0
    for fuente in fuentes:
        print(f"📡 Revisando {fuente['nombre']}...")
        try:
            feed = feedparser.parse(fuente['url'])
            for entry in feed.entries:
                link = entry.link
                
                if not ya_notificado(link):
                    # Solo le pasamos a la IA ofertas nuevas para ahorrar tokens
                    analisis = analizar_con_ia(cv_texto, entry.title, entry.get('summary', ''))
                    
                    if "MATCH: SI" in analisis.upper():
                        mensaje = (
                            f"✅ *¡NUEVO MATCH ENCONTRADO POR IA!*\n"
                            f"━━━━━━━━━━━━━━━━━━\n"
                            f"🏢 *Portal:* {fuente['nombre']}\n"
                            f"📌 *Puesto:* {entry.title}\n\n"
                            f"{analisis}\n\n"
                            f"🔗 [POSTULARSE AQUÍ]({link})"
                        )
                        enviar_telegram(mensaje)
                        registrar_job(link)
                        encontrados += 1
                        time.sleep(2) # Pausa para evitar spam
        except Exception as e:
            print(f"❌ Error en fuente {fuente['nombre']}: {e}")

    print(f"✨ Escaneo finalizado. Se encontraron {encontrados} oportunidades relevantes.")

# --- PLANIFICADOR (SCHEDULE) ---

if __name__ == "__main__":
    minutos = int(os.getenv("TIEMPO_ESPERA_MINUTOS", 60))
    
    print("🚀 Asistente de Empleo con IA Iniciado.")
    print(f"📅 Escaneo programado cada {minutos} minutos.")
    print("Presiona Ctrl+C para detener el bot.")

    # Ejecutar una vez al inicio
    ejecutar_escaneo()

    # Programar repeticiones
    schedule.every(minutos).minutes.do(ejecutar_escaneo)

    while True:
        schedule.run_pending()
        time.sleep(1)
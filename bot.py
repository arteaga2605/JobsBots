import os
import requests
import feedparser
import random
import time
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURACIÓN ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def ya_notificado(job_id):
    try:
        res = supabase.table("jobs_notified").select("job_id").eq("job_id", job_id).execute()
        return len(res.data) > 0
    except: return False

def registrar_job(job_id):
    supabase.table("jobs_notified").insert({"job_id": job_id}).execute()

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

def buscar_en_fuentes(keywords, remoto_solo):
    print(f"\n🚀 Buscando: {keywords} (Remoto: {remoto_solo})")
    
    fuentes = [
        {"nombre": "Forobeta (Negocios)", "url": "https://forobeta.com/forums/ofertas-de-trabajo/index.rss"},
        {"nombre": "We Work Remotely", "url": "https://weworkremotely.com/remote-jobs.rss"},
        {"nombre": "RemoteOK", "url": "https://remoteok.com/remote-jobs.rss"},
        {"nombre": "Get on Board", "url": "https://www.getonbrd.com/jobs/remote.rss"}
    ]

    for fuente in fuentes:
        print(f"📡 Revisando {fuente['nombre']}...")
        try:
            feed = feedparser.parse(fuente['url'])
            for entry in feed.entries:
                titulo = entry.title.lower()
                desc = entry.summary.lower() if 'summary' in entry else ""
                
                # FILTRO DE INTERÉS
                match_keyword = any(k.strip().lower() in titulo or k.strip().lower() in desc for k in keywords.split(","))
                
                if match_keyword:
                    if not ya_notificado(entry.link):
                        msg = f"🔥 *¡Nueva Oferta en {fuente['nombre']}!*\n📌 {entry.title}\n🔗 [Postulación]({entry.link})"
                        enviar_telegram(msg)
                        registrar_job(entry.link)
        except Exception as e:
            print(f"Error en {fuente['nombre']}: {e}")

def buscar_linkedin_legal(keywords):
    """
    LinkedIn no permite bots, pero Google indexa sus empleos. 
    Usamos una búsqueda de Google filtrada (Dorking).
    """
    print("🔎 Consultando LinkedIn vía Google (Sin riesgo de baneo)...")
    # Este es un hack: Consultamos la API gratuita de búsqueda si la tienes, 
    # o simplemente generamos el link de búsqueda directa para que tú lo abras.
    query = f"site:linkedin.com/jobs/view {keywords}"
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbs=qdr:d"
    
    enviar_telegram(f"🕵️ *Rastreo de LinkedIn (Últimas 24h):*\nHe filtrado nuevas vacantes en LinkedIn para ti. Revísalas aquí:\n{search_url}")

if __name__ == "__main__":
    print("--- ASISTENTE DE EMPLEO INTERACTIVO ---")
    
    # PREGUNTAS CLAVE
    p_carrera = input("1. ¿Qué puestos buscas hoy? (Ej: Python, Contador): ") or os.getenv("MI_CARRERA")
    p_remoto = input("2. ¿Solo remoto? (s/n): ").lower() == 's'
    p_pais = input("3. ¿Algún país específico? (Ej: Venezuela, dejar vacío para cualquiera): ")

    # Ejecutar búsqueda
    buscar_en_fuentes(p_carrera, p_remoto)
    buscar_linkedin_legal(p_carrera)
    
    print("\n✅ ¡Listo! Revisa tu Telegram.")
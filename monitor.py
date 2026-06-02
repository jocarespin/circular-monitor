import asyncio
from playwright.async_api import async_playwright
import hashlib
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import os

CIRCULAR_URL = "https://sites.google.com/view/myhnewsletter/unamuno/k2-a"
EMAIL_RECIPIENT = "carlos.espinoza@qualytech.mx"
EMAIL_SENDER = "carlos.espinoza@qualytech.mx"
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

VERSIONS_FILE = "versions.json"

def cargar_versiones():
    if os.path.exists(VERSIONS_FILE):
        with open(VERSIONS_FILE, 'r') as f:
            return json.load(f)
    return []

def guardar_version(contenido, estado):
    versiones = cargar_versiones()
    nueva_version = {
        "fecha": datetime.now().isoformat(),
        "contenido": contenido[:1000],
        "hash": hashlib.sha256(contenido.encode()).hexdigest()[:16],
        "estado": estado
    }
    versiones.append(nueva_version)
    with open(VERSIONS_FILE, 'w') as f:
        json.dump(versiones, f, indent=2)
    return nueva_version

def obtener_version_anterior():
    versiones = cargar_versiones()
    return versiones[-1] if versiones else None

async def capturar_pagina():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            await page.goto(CIRCULAR_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(3000)
            
            contenido = await page.evaluate("""
                () => {
                    return document.body.innerText;
                }
            """)
            
            await browser.close()
            return contenido
        except Exception as e:
            print(f"Error: {e}")
            await browser.close()
            return None

def procesar_contenido(contenido):
    lineas = contenido.split('\n')
    lineas_limpias = [l.strip() for l in lineas if l.strip() and len(l.strip()) > 10]
    
    palabras_clave = ['CIRCULAR', 'menú', 'evento', 'aviso', 'horario', 'lección', 'actividad']
    
    resumen = "📌 CONTENIDO PRINCIPAL:\n\n"
    encontrados = 0
    
    for linea in lineas_limpias:
        if encontrados >= 20:
            break
        if any(palabra.lower() in linea.lower() for palabra in palabras_clave):
            if 'google' not in linea.lower() and 'report' not in linea.lower():
                resumen += f"▪ {linea}\n"
                encontrados += 1
    
    if encontrados == 0:
        resumen += "\n".join(lineas_limpias[:15])
    
    return resumen

def detectar_cambios(contenido_nuevo, contenido_anterior):
    if not contenido_anterior:
        return {
            "hay_cambios": False,
            "tipo": "PRIMERA_LECTURA",
            "detalles": ["Primera ejecución"]
        }
    
    hash_nuevo = hashlib.sha256(contenido_nuevo.encode()).hexdigest()[:16]
    
    if hash_nuevo == contenido_anterior.get("hash"):
        return {
            "hay_cambios": False,
            "tipo": "SIN_CAMBIOS",
            "detalles": ["Sin cambios desde la última revisión"]
        }
    
    return {
        "hay_cambios": True,
        "tipo": "CAMBIOS_DETECTADOS",
        "detalles": ["Se detectaron cambios en la circular"]
    }

def enviar_email(asunto, resumen, cambios):
    try:
        fecha = datetime.now().strftime("%d/%m/%Y")
        hora = datetime.now().strftime("%H:%M:%S")
        
        status_icon = "✅" if cambios["hay_cambios"] else "⚠️"
        status_texto = "CAMBIOS" if cambios["hay_cambios"] else "SIN CAMBIOS"
        
        html = f"""
        <div style="font-family: Arial; color: #333;">
            <h2>📋 RESUMEN CIRCULAR K2-A</h2>
            <p><strong>Fecha:</strong> {fecha} | <strong>Hora:</strong> {hora}</p>
            <hr>
            <div style="background: #f0f4ff; padding: 15px; border-left: 4px solid #4285f4;">
                <h3>📌 RESUMEN EJECUTIVO</h3>
                <pre style="white-space: pre-wrap; font-family: Arial;">{resumen}</pre>
            </div>
            <hr>
            <h3>Estado: {status_icon} {status_texto}</h3>
            <ul>
                {"".join(f"<li>{d}</li>" for d in cambios["detalles"])}
            </ul>
        </div>
        """
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = asunto
        msg['From'] = EMAIL_SENDER
        msg['To'] = EMAIL_RECIPIENT
        msg.attach(MIMEText(html, 'html'))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        server.quit()
        
        print("✅ Email enviado")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    print("=== MONITOR INICIADO ===")
    
    contenido = await capturar_pagina()
    if not contenido:
        print("Error obteniendo contenido")
        return
    
    resumen = procesar_contenido(contenido)
    version_anterior = obtener_version_anterior()
    cambios = detectar_cambios(contenido, version_anterior)
    
    guardar_version(contenido, cambios['tipo'])
    
    fecha = datetime.now().strftime("%d/%m/%Y")
    asunto = f"[CIRCULAR K2-A] {cambios['tipo']} - {fecha}"
    
    enviar_email(asunto, resumen, cambios)
    print("=== COMPLETADO ===")

if __name__ == "__main__":
    asyncio.run(main())

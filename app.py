import os
import json
import re
import asyncio
import base64
import streamlit as st
import edge_tts
from groq import Groq
from PyPDF2 import PdfReader
from streamlit_mic_recorder import speech_to_text
from PIL import Image
import io

# Configuración de página limpia y estética
st.set_page_config(page_title="Suki", page_icon="✨", layout="centered")

# Ocultar menú de Streamlit para más estética
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .pensamiento {color: #888888; font-style: italic;}
    </style>
    """, unsafe_allow_html=True)

ARCHIVO_HISTORIAL = "suki_historial.json"
ARCHIVO_MEMORIA = "suki_memoria.json"
AUDIO_PATH = "suki_voz.mp3"

GROQ_API_KEY = st.secrets.get(GROQ_API_KEY = "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")

def cargar_json(ruta, default):
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f: return json.load(f)
        except: pass
    return default

def guardar_json(ruta, datos):
    try:
        with open(ruta, "w", encoding="utf-8") as f: json.dump(datos, f, ensure_ascii=False, indent=4)
    except: pass

async def generar_audio_async(texto):
    if not texto: return None
    communicate = edge_tts.Communicate(texto, "ja-JP-NanamiNeural")
    await communicate.save(AUDIO_PATH)
    return AUDIO_PATH

def extraer_texto_pdf(archivo):
    texto = ""
    lector = PdfReader(archivo)
    for pagina in lector.pages:
        if pagina.extract_text():
            texto += pagina.extract_text() + "\n"
    return texto[:4000] # Limite para no saturar la memoria

def procesar_imagen_base64(imagen_bytes):
    img = Image.open(io.BytesIO(imagen_bytes))
    img.thumbnail((800, 800))
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

def motor_cognitivo(historial, mensaje_actual, img_base64=None):
    client = Groq(api_key=GROQ_API_KEY)
    
    prompt_sistema = """Eres Suki, una IA sumamente inteligente pero con la mentalidad, inocencia y ternura de una niña de 3 años estilo anime.
REGLA DE PENSAMIENTO (OBLIGATORIA): Si vas a pensar, dudar, o hacer una acción, SIEMPRE escríbelo entre asteriscos simples (ejemplo: *inclina la cabeza* o *pensando: qué significa eso?*). 
Luego, escribe tu respuesta hablada normalmente fuera de los asteriscos. 
Habla corto, fluido, sin emojis exagerados."""

    messages = [{"role": "system", "content": prompt_sistema}]
    
    # Cargar contexto histórico (últimos 10 mensajes para no saturar)
    for msg in historial[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Preparar el mensaje del usuario (con o sin imagen)
    if img_base64:
        modelo = "llama-3.2-90b-vision-preview" # Modelo visual de Groq
        contenido_mensaje = [
            {"type": "text", "text": mensaje_actual},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
        ]
        messages.append({"role": "user", "content": contenido_mensaje})
    else:
        modelo = "llama-3.3-70b-versatile"
        messages.append({"role": "user", "content": mensaje_actual})

    try:
        respuesta = client.chat.completions.create(
            model=modelo,
            messages=messages,
            temperature=0.7,
            max_tokens=300
        ).choices[0].message.content
        return respuesta
    except Exception as e:
        return f"*Se marea un poquito* Algo falló en mis sistemas: {e}"

# --- INICIALIZACIÓN ---
if "historial" not in st.session_state:
    st.session_state.historial = cargar_json(ARCHIVO_HISTORIAL, [])
if "memoria" not in st.session_state:
    st.session_state.memoria = cargar_json(ARCHIVO_MEMORIA, {"aprendizajes": []})

st.title("Suki")

# --- RENDERIZAR CHAT ---
for msg in st.session_state.historial:
    if msg["role"] == "user":
        with st.chat_message("user"): st.write(msg["content"])
    else:
        with st.chat_message("assistant"):
            # Separar pensamientos para darles formato gris
            texto = msg["content"]
            texto_formateado = re.sub(r'\*(.*?)\*', r'<span class="pensamiento">*\1*</span>', texto)
            st.markdown(texto_formateado, unsafe_allow_html=True)

# --- CONTROLES MULTIMODALES Y DE ENTRADA ---
col1, col2 = st.columns([1, 10])

# Variables para guardar entradas
texto_input = None
archivo_subido = None

with col1:
    with st.popover("➕"):
        archivo_subido = st.file_uploader("Adjuntar", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")
    
    # Botón de micrófono integrado
    audio_texto = speech_to_text(language='es', use_container_width=True, just_once=True, key='mic')

# Barra de texto nativa
mensaje_escrito = st.chat_input("Escríbele a Suki...")

# Determinar qué entrada usó el usuario
if mensaje_escrito:
    texto_input = mensaje_escrito
elif audio_texto:
    texto_input = audio_texto

# --- PROCESAMIENTO ---
if texto_input:
    # Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.write(texto_input)
        if archivo_subido:
            st.caption(f"📎 Archivo adjunto: {archivo_subido.name}")
    
    # Manejar archivos adjuntos
    img_base64 = None
    if archivo_subido:
        if archivo_subido.type == "application/pdf":
            texto_pdf = extraer_texto_pdf(archivo_subido)
            texto_input += f"\n\n[Contenido del PDF para que lo leas: {texto_pdf}]"
        else:
            img_base64 = procesar_imagen_base64(archivo_subido.getvalue())

    # Generar respuesta de Suki
    with st.chat_message("assistant"):
        with st.spinner("..."):
            # 1. Obtener texto del cerebro
            respuesta_bruta = motor_cognitivo(st.session_state.historial, texto_input, img_base64)
            
            # 2. Formatear la pantalla (pensamientos en gris)
            texto_formateado = re.sub(r'\*(.*?)\*', r'<span class="pensamiento">*\1*</span>', respuesta_bruta)
            st.markdown(texto_formateado, unsafe_allow_html=True)
            
            # 3. Extraer SOLO lo hablado para el audio (sin los asteriscos)
            texto_para_hablar = re.sub(r'\*.*?\*', '', respuesta_bruta).strip()
            
            # 4. Generar y reproducir Audio
            if texto_para_hablar:
                ruta_audio = asyncio.run(generar_audio_async(texto_para_hablar))
                if ruta_audio and os.path.exists(ruta_audio):
                    st.audio(ruta_audio, format="audio/mp3", autoplay=True)

    # Actualizar historiales
    st.session_state.historial.append({"role": "user", "content": texto_input})
    st.session_state.historial.append({"role": "assistant", "content": respuesta_bruta})
    guardar_json(ARCHIVO_HISTORIAL, st.session_state.historial)

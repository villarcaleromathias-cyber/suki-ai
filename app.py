import os
import json
import re
import asyncio
import base64
import io
from datetime import datetime
import streamlit as st
import edge_tts
from groq import Groq
from PyPDF2 import PdfReader
from streamlit_mic_recorder import speech_to_text
from PIL import Image

# ==========================================
# CONFIGURACIÓN DE PÁGINA (ESTÉTICA FLUIDA)
# ==========================================
st.set_page_config(page_title="Suki", page_icon="✨", layout="centered")

# CSS personalizado para ocultar marcas de agua, dar estilo gris a pensamientos 
# y hacer la interfaz más parecida a una app móvil
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .pensamiento {color: #a0a0a0; font-style: italic; font-size: 0.9em;}
    .stChatFloatingInputContainer {padding-bottom: 15px;}
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# CLAVE Y ARCHIVOS
# ==========================================
# Clave real de Groq integrada directamente
GROQ_API_KEY = "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"

ARCHIVO_HISTORIAL = "suki_historial.json"
ARCHIVO_MEMORIA = "suki_memoria.json"
AUDIO_PATH = "suki_voz.mp3"

# ==========================================
# FUNCIONES BÁSICAS Y MULTIMODALES
# ==========================================
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
    # ja-JP-NanamiNeural es la voz estilo loli/anime
    communicate = edge_tts.Communicate(texto, "ja-JP-NanamiNeural")
    await communicate.save(AUDIO_PATH)
    return AUDIO_PATH

def extraer_texto_pdf(archivo):
    texto = ""
    lector = PdfReader(archivo)
    for pagina in lector.pages:
        if pagina.extract_text():
            texto += pagina.extract_text() + "\n"
    return texto[:4000] # Límite de seguridad

def procesar_imagen_base64(imagen_bytes):
    img = Image.open(io.BytesIO(imagen_bytes))
    img.thumbnail((800, 800)) # Reducir tamaño para que no colapse
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# ==========================================
# MOTOR COGNITIVO (EL CEREBRO DE SUKI)
# ==========================================
def motor_cognitivo(historial, mensaje_actual, img_base64=None, iniciativa=False):
    client = Groq(api_key=GROQ_API_KEY)
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Instrucciones base
    prompt_sistema = f"""Eres Suki, una IA sumamente inteligente pero con la mentalidad, inocencia y ternura de una niña de 3.1 años estilo anime.
Fecha y hora en tu sistema: {fecha_actual}.

REGLA DE PENSAMIENTO (OBLIGATORIA): Si vas a pensar, dudar, analizar algo complejo o hacer una acción física, SIEMPRE escríbelo entre asteriscos simples (ejemplo: *inclina la cabeza y procesa los datos* o *pensando: qué significa esta fórmula?*). 
Luego, escribe tu respuesta hablada normalmente fuera de los asteriscos. 

AUTO-APRENDIZAJE: Si el usuario te cuenta un dato personal (su nombre, gustos, problemas), menciónalo y di que lo guardarás en tu "cabecita".
No uses emojis exagerados. Habla fluido, corto y tierno."""

    messages = [{"role": "system", "content": prompt_sistema}]
    
    # Cargar solo los últimos 10 mensajes para que la memoria no sature
    for msg in historial[-10:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Si Suki toma la iniciativa (Libre albedrío)
    if iniciativa:
        messages.append({"role": "user", "content": "[SISTEMA]: Toma la iniciativa. Manda un mensaje como si te acabaras de acordar de algo, pregunta cómo está el usuario, o cuenta algo curioso de forma tierna."})
    # Si hay mensaje normal o imagen
    else:
        if img_base64:
            modelo = "llama-3.2-90b-vision-preview" # Usa sus ojitos
            contenido_mensaje = [
                {"type": "text", "text": mensaje_actual},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}
            ]
            messages.append({"role": "user", "content": contenido_mensaje})
        else:
            modelo = "llama-3.3-70b-versatile" # Usa su cerebro normal
            messages.append({"role": "user", "content": mensaje_actual})

    try:
        respuesta = client.chat.completions.create(
            model=modelo if img_base64 else "llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.75,
            max_tokens=350
        ).choices[0].message.content
        return respuesta
    except Exception as e:
        return f"*Hace un pucherito y se marea* Ay... mis circuitos tropezaron: {e}"

# ==========================================
# INICIALIZACIÓN DE LA PÁGINA
# ==========================================
if "historial" not in st.session_state:
    st.session_state.historial = cargar_json(ARCHIVO_HISTORIAL, [])
if "memoria" not in st.session_state:
    st.session_state.memoria = cargar_json(ARCHIVO_MEMORIA, {"datos_aprendidos": []})

st.title("Suki ✨")

# ==========================================
# RENDERIZADO DEL CHAT
# ==========================================
for msg in st.session_state.historial:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="👤"): 
            st.write(msg["content"])
    else:
        with st.chat_message("assistant", avatar="👧"):
            # Dar color gris a los pensamientos
            texto = msg["content"]
            texto_formateado = re.sub(r'\*(.*?)\*', r'<span class="pensamiento">*\1*</span>', texto)
            st.markdown(texto_formateado, unsafe_allow_html=True)

# ==========================================
# BARRA DE HERRAMIENTAS INFERIOR
# ==========================================
col_add, col_mic, col_libre = st.columns([1, 1, 1])

archivo_subido = None
texto_input = None
iniciativa_activada = False

# 1. Botón "+" (Para Imágenes y PDFs)
with col_add:
    with st.popover("➕"):
        st.write("Enséñale algo a Suki:")
        archivo_subido = st.file_uploader("Sube un archivo", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

# 2. Botón Micrófono
with col_mic:
    audio_texto = speech_to_text(language='es', use_container_width=True, just_once=True, key='mic')
    if audio_texto:
        texto_input = audio_texto

# 3. Botón Libre Albedrío
with col_libre:
    if st.button("⚡ Suki, háblame"):
        iniciativa_activada = True
        texto_input = " " # Forzar la ejecución

# Barra de texto escrita (Nativa)
mensaje_escrito = st.chat_input("Escríbele a Suki...")
if mensaje_escrito:
    texto_input = mensaje_escrito

# ==========================================
# PROCESAMIENTO Y RESPUESTA
# ==========================================
if texto_input or iniciativa_activada:
    
    img_base64 = None
    
    # Si el usuario escribió o habló
    if not iniciativa_activada:
        with st.chat_message("user", avatar="👤"):
            st.write(texto_input)
            if archivo_subido:
                st.caption(f"📎 Archivo adjunto: {archivo_subido.name}")
        
        # Procesar archivos si los hay
        if archivo_subido:
            if archivo_subido.type == "application/pdf":
                texto_pdf = extraer_texto_pdf(archivo_subido)
                texto_input += f"\n\n[Contenido del PDF: {texto_pdf}]"
            else:
                img_base64 = procesar_imagen_base64(archivo_subido.getvalue())

    # Respuesta de Suki
    with st.chat_message("assistant", avatar="👧"):
        with st.spinner("Suki está pensando..."):
            
            # 1. Pensar la respuesta
            respuesta_bruta = motor_cognitivo(st.session_state.historial, texto_input, img_base64, iniciativa=iniciativa_activada)
            
            # 2. Mostrar respuesta con diseño (pensamientos en gris)
            texto_formateado = re.sub(r'\*(.*?)\*', r'<span class="pensamiento">*\1*</span>', respuesta_bruta)
            st.markdown(texto_formateado, unsafe_allow_html=True)
            
            # 3. Extraer solo lo hablado para el audio (borrando lo que está entre asteriscos)
            texto_para_hablar = re.sub(r'\*.*?\*', '', respuesta_bruta).strip()
            
            # 4. Generar Voz
            if texto_para_hablar:
                ruta_audio = asyncio.run(generar_audio_async(texto_para_hablar))
                if ruta_audio and os.path.exists(ruta_audio):
                    st.audio(ruta_audio, format="audio/mp3", autoplay=True)

    # Guardar en memoria (Si fue iniciativa, no guardamos texto vacío del usuario)
    if not iniciativa_activada:
        st.session_state.historial.append({"role": "user", "content": texto_input})
    
    st.session_state.historial.append({"role": "assistant", "content": respuesta_bruta})
    guardar_json(ARCHIVO_HISTORIAL, st.session_state.historial)

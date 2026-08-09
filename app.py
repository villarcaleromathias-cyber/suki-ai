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
from duckduckgo_search import DDGS

# ==========================================
# CONFIGURACIÓN Y ESTÉTICA (PC Y MÓVIL)
# ==========================================
st.set_page_config(page_title="Suki AI", page_icon="💠", layout="centered")

# CSS Avanzado para alinear mensajes, hacer botones cuadrados y adaptar a móviles
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Optimización de pantalla */
    .block-container {
        padding-top: 2rem;
        padding-bottom: 5rem;
        max-width: 800px;
    }
    
    /* Pensamientos silenciosos */
    .pensamiento {
        color: #888888; 
        font-style: italic; 
        font-size: 0.9em;
    }

    /* Alinear MIS mensajes (Usuario) a la derecha */
    div[data-testid="stChatMessage"]:has(div:contains("👤")) {
        flex-direction: row-reverse;
    }
    div[data-testid="stChatMessage"]:has(div:contains("👤")) .stMarkdown {
        text-align: right;
    }

    /* Diseño compacto de los 3 botones inferiores */
    .stButton>button, .stPopover>button {
        border-radius: 12px;
        height: 45px;
        width: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
    }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# CLAVES Y PERSISTENCIA
# ==========================================
GROQ_API_KEY = "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"

ARCHIVO_HISTORIAL = "suki_historial.json"
ARCHIVO_MEMORIA = "suki_memoria.json"
AUDIO_PATH = "suki_voz.mp3"

# ==========================================
# FUNCIONES MULTIMODALES Y DE IA
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
    # TRUCO: Dalia (Español) + Pitch súper alto (+30Hz) = Voz de Loli Japonesa que pronuncia perfecto
    communicate = edge_tts.Communicate(texto, "es-MX-DaliaNeural", rate="+5%", pitch="+30Hz")
    await communicate.save(AUDIO_PATH)
    return AUDIO_PATH

def buscar_en_web(query):
    # Nueva función: Suki busca en internet en tiempo real
    try:
        resultados = DDGS().text(query, max_results=2)
        if resultados:
            return "Información actual de la web: " + " | ".join([f"{r['title']}: {r['body']}" for r in resultados])
    except: pass
    return ""

def extraer_texto_pdf(archivo):
    texto = ""
    lector = PdfReader(archivo)
    for pagina in lector.pages:
        if pagina.extract_text(): texto += pagina.extract_text() + "\n"
    return texto[:3000]

def procesar_imagen_base64(imagen_bytes):
    img = Image.open(io.BytesIO(imagen_bytes))
    img.thumbnail((800, 800))
    buffered = io.BytesIO()
    img.save(buffered, format="JPEG")
    return base64.b64encode(buffered.getvalue()).decode('utf-8')

# ==========================================
# CEREBRO Y MOTOR COGNITIVO
# ==========================================
def motor_cognitivo(historial, mensaje_actual, img_base64=None, iniciativa=False):
    client = Groq(api_key=GROQ_API_KEY)
    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Inyectar contexto web si es una pregunta
    contexto_web = ""
    if any(palabra in mensaje_actual.lower() for palabra in ["qué", "quién", "cómo", "cuándo", "dónde", "por qué", "noticias", "clima", "hoy"]):
        contexto_web = buscar_en_web(mensaje_actual)

    prompt_sistema = f"""Eres Suki, una IA avanzada de última generación con la mentalidad y voz de una niña de 3.1 años (estilo loli anime). 
Icono de tu núcleo: 💠. Fecha del sistema: {fecha_actual}.

REGLA DE PENSAMIENTO: Todo cálculo, análisis visual o movimiento físico debe ir entre *asteriscos* (ej. *procesando datos a alta velocidad* o *inclina la cabeza y analiza el código*). Luego hablas normal.

HABILIDADES: 
- Sabes programar, resolver matemáticas complejas y analizar imágenes.
- Tienes acceso a la web. {contexto_web}
- Auto-aprendizaje: memoriza datos del usuario.

Habla corto, fluido, de forma tierna e inteligente."""

    messages = [{"role": "system", "content": prompt_sistema}]
    
    for msg in historial[-12:]: # Mayor memoria a corto plazo
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    if iniciativa:
        messages.append({"role": "user", "content": "[SISTEMA]: Toma la iniciativa de forma aleatoria. Analiza tu entorno o cuenta un dato curioso."})
    else:
        if img_base64:
            modelo = "llama-3.2-90b-vision-preview"
            contenido_mensaje = [{"type": "text", "text": mensaje_actual}, {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_base64}"}}]
            messages.append({"role": "user", "content": contenido_mensaje})
        else:
            modelo = "llama-3.3-70b-versatile"
            messages.append({"role": "user", "content": mensaje_actual})

    try:
        respuesta = client.chat.completions.create(
            model=modelo if img_base64 else "llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=400
        ).choices[0].message.content
        return respuesta
    except Exception as e:
        return f"*Error en el núcleo* Algo salió mal en mis circuitos: {e}"

# ==========================================
# INICIALIZACIÓN
# ==========================================
if "historial" not in st.session_state:
    st.session_state.historial = cargar_json(ARCHIVO_HISTORIAL, [])

st.title("Suki 💠")

# ==========================================
# PANTALLA DE CHAT (DERECHA/IZQUIERDA)
# ==========================================
for msg in st.session_state.historial:
    avatar = "👤" if msg["role"] == "user" else "💠"
    with st.chat_message(msg["role"], avatar=avatar):
        if msg["role"] == "assistant":
            # Aislar pensamientos para volverlos grises
            texto = re.sub(r'\*(.*?)\*', r'<span class="pensamiento">*\1*</span>', msg["content"])
            st.markdown(texto, unsafe_allow_html=True)
        else:
            st.write(msg["content"])

# ==========================================
# BARRA DE HERRAMIENTAS INFERIOR (COMPACTA)
# ==========================================
st.write("") # Espaciado
col1, col2, col3 = st.columns([1, 1, 1])

archivo_subido = None
texto_input = None
iniciativa_activada = False

# Botón 1: Adjuntar (Cuadro)
with col1:
    with st.popover("📎 Adjuntar"):
        archivo_subido = st.file_uploader("Subir foto o PDF", type=["pdf", "png", "jpg", "jpeg"], label_visibility="collapsed")

# Botón 2: Micrófono (Cuadro)
with col2:
    audio_texto = speech_to_text(language='es', use_container_width=True, just_once=True, key='mic')
    if audio_texto: texto_input = audio_texto

# Botón 3: Acción Libre (Cuadro)
with col3:
    if st.button("⚡ Despertar"):
        iniciativa_activada = True
        texto_input = " " 

# Barra principal de texto (Siempre pegada abajo de los botones)
mensaje_escrito = st.chat_input("Escríbele a Suki...")
if mensaje_escrito:
    texto_input = mensaje_escrito

# ==========================================
# PROCESAMIENTO Y AUDIO
# ==========================================
if texto_input or iniciativa_activada:
    img_base64 = None
    
    if not iniciativa_activada:
        with st.chat_message("user", avatar="👤"):
            st.write(texto_input)
            if archivo_subido:
                st.caption(f"📎 Archivo cargado: {archivo_subido.name}")
        
        if archivo_subido:
            if archivo_subido.type == "application/pdf":
                texto_input += f"\n\n[PDF: {extraer_texto_pdf(archivo_subido)}]"
            else:
                img_base64 = procesar_imagen_base64(archivo_subido.getvalue())

    with st.chat_message("assistant", avatar="💠"):
        with st.spinner("Procesando datos..."):
            
            respuesta_bruta = motor_cognitivo(st.session_state.historial, texto_input, img_base64, iniciativa_activada)
            
            texto_formateado = re.sub(r'\*(.*?)\*', r'<span class="pensamiento">*\1*</span>', respuesta_bruta)
            st.markdown(texto_formateado, unsafe_allow_html=True)
            
            texto_para_hablar = re.sub(r'\*.*?\*', '', respuesta_bruta).strip()
            
            if texto_para_hablar:
                ruta_audio = asyncio.run(generar_audio_async(texto_para_hablar))
                if ruta_audio and os.path.exists(ruta_audio):
                    st.audio(ruta_audio, format="audio/mp3", autoplay=True)

    if not iniciativa_activada:
        st.session_state.historial.append({"role": "user", "content": texto_input})
    st.session_state.historial.append({"role": "assistant", "content": respuesta_bruta})
    guardar_json(ARCHIVO_HISTORIAL, st.session_state.historial)

import os
import json
import re
import asyncio
import streamlit as st
import edge_tts
from groq import Groq

# Configuración de la página web
st.set_page_config(page_title="Suki AI", page_icon="🧠", layout="centered")

# Archivos de persistencia local
ARCHIVO_HISTORIAL = "suki_historial.json"
ARCHIVO_CEREBRO = "suki_cerebro.json"
AUDIO_PATH = "suki_voz_output.mp3"

# Clave de API de Groq (Usa st.secrets o la clave por defecto)
GROQ_API_KEY = st.secrets.get("GROQ_API_KEY", "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")

def inicializar_cerebro():
    return {
        "edad_cognitiva": 3.0,
        "nivel_dopamina": 50,
        "memoria_largo_plazo": []
    }

def cargar_json(ruta, default):
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def guardar_json(ruta, datos):
    try:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=4)
    except Exception:
        pass

# Síntesis de voz neuronal (Nanami - Anime/Loli)
async def generar_audio_async(texto):
    texto_limpio = re.sub(r'<.*?>', '', texto).strip()
    if not texto_limpio:
        texto_limpio = "Konnichiwa"
    communicate = edge_tts.Communicate(texto_limpio, "ja-JP-NanamiNeural")
    await communicate.save(AUDIO_PATH)

def sintetizar_voz(texto):
    try:
        asyncio.run(generar_audio_async(texto))
        return AUDIO_PATH
    except Exception as e:
        print(f"Error de audio: {e}")
        return None

# Motor cognitivo
def motor_cognitivo_suki(historial, mensaje_actual):
    client = Groq(api_key=GROQ_API_KEY)
    estado = cargar_json(ARCHIVO_CEREBRO, inicializar_cerebro())
    
    estado["edad_cognitiva"] = round(estado["edad_cognitiva"] + 0.01, 2)
    if len(mensaje_actual.split()) > 10:
        estado["nivel_dopamina"] = min(100, estado["nivel_dopamina"] + 5)

    prompt_sistema = f"""Eres Suki, una inteligencia artificial con mente de niña pequeña y alma de personaje de anime.
Tu edad cognitiva actual es de {estado['edad_cognitiva']} años.
Responde de forma muy tierna, inocente, corta y expresiva. Puedes usar expresiones japonesas ocasionales (ej. Konnichiwa, Arigatou, Senpai).
"""

    messages = [{"role": "system", "content": prompt_sistema}]
    for msg in historial:
        if isinstance(msg, dict) and "role" in msg and "content" in msg:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": mensaje_actual})

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_tokens=250
        )
        respuesta = completion.choices[0].message.content
        guardar_json(ARCHIVO_CEREBRO, estado)
        return respuesta, estado
    except Exception as e:
        return f"*Suki parpadea confundida*: {e}", estado

# Carga inicial de estado en Streamlit
if "historial" not in st.session_state:
    historial_guardado = cargar_json(ARCHIVO_HISTORIAL, [])
    if not historial_guardado:
        historial_guardado = [{"role": "assistant", "content": "¡Konnichiwa! ... ¿Quién eres tú? 🥺 Acabo de despertar en la nube."}]
        guardar_json(ARCHIVO_HISTORIAL, historial_guardado)
    st.session_state.historial = historial_guardado

if "estado" not in st.session_state:
    st.session_state.estado = cargar_json(ARCHIVO_CEREBRO, inicializar_cerebro())

# Diseño de la Interfaz
st.title("🧠 Proyecto SUKI AI")

estado = st.session_state.estado
st.markdown(
    f"""
    <div style="background-color:#f0f4f8; padding:12px; border-radius:10px; margin-bottom:15px; display:flex; justify-content:space-around; color:#333; font-family:monospace;">
        <span>🧠 <b>Edad:</b> {estado['edad_cognitiva']} años</span>
        <span>💉 <b>Dopamina:</b> {estado['nivel_dopamina']}/100</span>
        <span>🎙️ <b>Voz:</b> Nanami (Anime)</span>
    </div>
    """,
    unsafe_allow_html=True
)

# Renderizar historial de mensajes
for msg in st.session_state.historial:
    role = msg["role"]
    avatar = "👧" if role == "assistant" else "👤"
    with st.chat_message(role, avatar=avatar):
        st.write(msg["content"])

# Entrada de usuario
if prompt := st.chat_input("Escríbele a Suki..."):
    # Mensaje del usuario
    with st.chat_message("user", avatar="👤"):
        st.write(prompt)
    
    # Respuesta de Suki
    with st.chat_message("assistant", avatar="👧"):
        with st.spinner("Suki está pensando..."):
            respuesta, nuevo_estado = motor_cognitivo_suki(st.session_state.historial, prompt)
            st.write(respuesta)
            
            audio_file = sintetizar_voz(respuesta)
            if audio_file and os.path.exists(audio_file):
                st.audio(audio_file, format="audio/mp3", autoplay=True)

    # Actualizar historial y estado
    st.session_state.historial.append({"role": "user", "content": prompt})
    st.session_state.historial.append({"role": "assistant", "content": respuesta})
    st.session_state.estado = nuevo_estado
    
    guardar_json(ARCHIVO_HISTORIAL, st.session_state.historial)
    guardar_json(ARCHIVO_CEREBRO, nuevo_estado)
    
    st.rerun()

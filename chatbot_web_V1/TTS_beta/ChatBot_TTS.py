import os
import sys
import io
import streamlit as st
import google.generativeai as genai
from gtts import gTTS  # 需安裝: pip install gTTS

# 將父目錄加入 sys.path 以便匯入 chatbot_logic
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 匯入模組化的邏輯
from chatbot_logic import GeminiChatService

# 設定 Streamlit 頁面
st.set_page_config(page_title="Gemini ChatBot (語音版)", page_icon="🤖", layout="centered")
st.title("Gemini ChatBot (語音版)")

# 側邊欄：模型選擇
with st.sidebar:
    st.header("設定")
    # 新增 API Key 輸入欄位
    api_key = st.text_input("請輸入 Google API Key", type="password")
    
    # 使用目前有效的模型列表
    model_options = ["gemini-2.5-flash-tts"]

    if api_key:
        # 使用 .strip() 去除可能不小心複製到的換行符號或空白
        os.environ["GOOGLE_API_KEY"] = api_key.strip()

    selected_model = st.selectbox("選擇模型", model_options, index=0)

# 檢查是否已設定 API Key
if not os.environ.get("GOOGLE_API_KEY"):
    st.warning("請先在左側欄位輸入 Google API Key 才能啟動聊天機器人")
    st.stop()

# 初始化或更新 Chat Service
if "chat_service" not in st.session_state or st.session_state.get("current_model") != selected_model:
    st.session_state.current_model = selected_model
    st.session_state.chat_service = GeminiChatService(model_name=selected_model)
    st.session_state.chat_service.start_chat(history=[])

if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.chat_service.start_chat(history=[])

# 側邊欄：功能按鈕
with st.sidebar:
    if st.button("清除紀錄", type="primary"):
        st.session_state.messages = []
        st.session_state.chat_service.start_chat(history=[])
        st.rerun()

# 顯示對話紀錄
for message in st.session_state.messages:
    role = message.get("role", "user")
    if role == "model":
        role = "assistant"
    
    with st.chat_message(role):
        st.markdown(message.get("content", ""))

# 處理使用者輸入
if prompt := st.chat_input("請輸入訊息..."):
    # 1. 顯示使用者訊息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. 顯示 AI 回應
    with st.chat_message("assistant"):
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # 呼叫 ChatService 取得回應串流
            response_stream = st.session_state.chat_service.send_message(prompt)
            
            for chunk in response_stream:
                if hasattr(chunk, 'text'):
                    full_response += chunk.text
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "model", "content": full_response})

            # 3. TTS 語音生成與播放
            try:
                # 將文字轉為語音 (lang='zh-tw' 為中文，可依需求改為 'en')
                tts = gTTS(text=full_response, lang='zh-tw')
                audio_fp = io.BytesIO()
                tts.write_to_fp(audio_fp)
                st.audio(audio_fp, format='audio/mp3')
            except Exception as e:
                st.warning(f"無法產生語音: {e}")
                
        except Exception as e:
            st.error(f"發生錯誤: {e}")
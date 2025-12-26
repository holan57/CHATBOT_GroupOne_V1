import os
import sys
import streamlit as st
import google.generativeai as genai

# 將父目錄加入 sys.path 以便匯入 chatbot_logic
# 因為 chatbot_logic.py 位於上一層目錄
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 匯入模組化的邏輯
from chatbot_logic import GeminiChatService

# 設定 Streamlit 頁面
st.set_page_config(page_title="Gemini ChatBot", page_icon="🤖", layout="centered")
st.title("Gemini ChatBot")

# 側邊欄：模型選擇
with st.sidebar:
    st.header("設定")
    # 新增 API Key 輸入欄位
    api_key = st.text_input("請輸入 Google API Key", type="password")
    submit_btn = st.button("確認金鑰")
    
    # 指定模型列表 這行不要動
    model_options = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash-tts","gemini-3-flash"]

    if "key_valid" not in st.session_state:
        st.session_state.key_valid = False
    if "last_checked_key" not in st.session_state:
        st.session_state.last_checked_key = None

    if submit_btn or (api_key and api_key != st.session_state.last_checked_key):
        st.session_state.last_checked_key = api_key
        try:
            genai.configure(api_key=api_key.strip())
            list(genai.list_models())
            st.session_state.key_valid = True
            os.environ["GOOGLE_API_KEY"] = api_key.strip()
        except:
            st.session_state.key_valid = False
            if "GOOGLE_API_KEY" in os.environ:
                del os.environ["GOOGLE_API_KEY"]

    if st.session_state.key_valid and api_key:
        os.environ["GOOGLE_API_KEY"] = api_key.strip()

    selected_model = st.selectbox("選擇模型", model_options, index=0)

if st.session_state.get("last_checked_key"):
    if st.session_state.key_valid:
        st.success("歡迎使用!")
    else:
        st.error("請使用正確的金鑰")

# 檢查是否已設定 API Key，若無則停止執行並提示使用者
if not os.environ.get("GOOGLE_API_KEY"):
    if not st.session_state.get("last_checked_key"):
        st.warning("請先在左側欄位輸入 Google API Key 才能啟動聊天機器人")
    st.stop()

# 初始化或更新 Chat Service (當第一次執行或模型改變時)
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
    # 將 Gemini 的 "model" 角色轉換為 Streamlit 的 "assistant" 以正確顯示圖示
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

    # 2. 顯示 AI 回應 (串流顯示)
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
            
            # 3. 更新並儲存紀錄
            st.session_state.messages.append({"role": "model", "content": full_response})
                
        except Exception as e:
            st.error(f"發生錯誤: {e}")
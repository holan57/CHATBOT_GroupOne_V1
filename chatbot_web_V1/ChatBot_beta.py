import os
import sys
import streamlit as st
import google.generativeai as genai

# 將父目錄加入 sys.path 以便匯入 chatbot_logic
# 因為 chatbot_logic.py 位於上一層目錄
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 匯入模組化的邏輯
from chatbot_logic import GeminiChatService

# 設定 Streamlit 頁面配置，包含標題、圖示和版面配置
st.set_page_config(page_title="Gemini ChatBot", page_icon="🤖", layout="centered")
st.title("Gemini ChatBot")

# 側邊欄區塊：用於放置設定選項，如 API Key 和模型選擇
with st.sidebar:
    st.header("設定")
    # 建立一個密碼輸入框讓使用者輸入 Google API Key
    api_key = st.text_input("請輸入 Google API Key", type="password", key="api_key_input")
    submit_btn = st.button("確認金鑰")
    
    # 新增清除 Key 的按鈕
    if st.button("清除 Key"):
        # 清除 session_state 中的所有內容 (包含 Key 和對話紀錄)
        st.session_state.clear()
        st.session_state["api_key_input"] = ""
        st.rerun()

    # 定義可用的 Gemini 模型列表
    model_options = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-flash-tts","gemini-3-flash"]

    # 初始化 session_state 中的變數，用於追蹤金鑰驗證狀態
    # st.session_state 是 Streamlit 用來在不同次執行間保存變數的地方
    if "key_valid" not in st.session_state:
        st.session_state.key_valid = False
    if "last_checked_key" not in st.session_state:
        st.session_state.last_checked_key = None

    # 當使用者按下確認按鈕，或輸入了新的金鑰時執行驗證
    if submit_btn or (api_key and api_key != st.session_state.last_checked_key):
        st.session_state.last_checked_key = api_key
        try:
            # 嘗試設定金鑰並列出模型，如果成功代表金鑰有效
            genai.configure(api_key=api_key.strip())
            list(genai.list_models())
            st.session_state.key_valid = True
            # 將有效的金鑰存入 session_state，供後續邏輯使用 (取代 os.environ 以避免殘留)
            st.session_state.api_key = api_key.strip()
        except:
            # 如果驗證失敗，標記為無效並移除環境變數
            st.session_state.key_valid = False

    # 如果金鑰有效且存在，確保 session_state 已設定
    if st.session_state.key_valid and api_key and "api_key" not in st.session_state:
        st.session_state.api_key = api_key.strip()

    # 下拉式選單讓使用者選擇模型
    selected_model = st.selectbox("選擇模型", model_options, index=0)

# 根據驗證結果顯示提示訊息
if st.session_state.get("last_checked_key"):
    if st.session_state.key_valid:
        st.success("歡迎使用!")
    else:
        st.error("請使用正確的金鑰")

# 檢查環境變數中是否有 API Key，如果沒有則停止程式執行
# 這是為了防止在沒有金鑰的情況下呼叫 API 導致錯誤
if not os.environ.get("GOOGLE_API_KEY") and not st.session_state.get("api_key"):
    if not st.session_state.get("last_checked_key"):
        st.warning("請先在左側欄位輸入 Google API Key 才能啟動聊天機器人")
    st.stop() # 停止執行後續程式碼

# 初始化或更新 Chat Service
# 當 session_state 中沒有 chat_service，或者使用者切換了模型時執行
if "chat_service" not in st.session_state or st.session_state.get("current_model") != selected_model:
    st.session_state.current_model = selected_model
    # 建立新的 GeminiChatService 實例
    # 優先使用 session_state 中的 api_key，若無則 Service 會自動嘗試讀取環境變數
    st.session_state.chat_service = GeminiChatService(model_name=selected_model, api_key=st.session_state.get("api_key"))
    
    # 開始新的對話
    st.session_state.chat_service.start_chat(history=[])

# 初始化訊息列表，用於儲存對話紀錄以便在介面上顯示
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.chat_service.start_chat(history=[])

# 側邊欄按鈕：清除對話紀錄
with st.sidebar:
    if st.button("清除紀錄", type="primary"):
        # 清空訊息列表
        st.session_state.messages = []
        # 重置後端 API 的對話狀態
        st.session_state.chat_service.start_chat(history=[])
        # 重新執行 Streamlit 應用程式以更新介面
        st.rerun()

# 遍歷並顯示所有歷史訊息
for message in st.session_state.messages:
    role = message.get("role", "user")
    # 將 Gemini 的 "model" 角色名稱轉換為 Streamlit 介面用的 "assistant"
    if role == "model":
        role = "assistant"
    
    # 使用 st.chat_message 建立對應角色的訊息框
    with st.chat_message(role):
        st.markdown(message.get("content", ""))

# 處理使用者輸入
# st.chat_input 會在頁面底部顯示輸入框，當使用者發送訊息時回傳內容
if prompt := st.chat_input("請輸入訊息..."):
    # 1. 在介面上顯示使用者的訊息
    with st.chat_message("user"):
        st.markdown(prompt)
    # 將使用者訊息加入 session_state 紀錄
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. 處理 AI 回應
    with st.chat_message("assistant"):
        # 建立一個空的容器，用於即時更新串流回應
        message_placeholder = st.empty()
        full_response = ""
        
        try:
            # 呼叫後端邏輯傳送訊息，並取得回應串流 (Generator)
            response_stream = st.session_state.chat_service.send_message(prompt)
            
            # 逐塊讀取回應並更新介面，產生打字機效果
            for chunk in response_stream:
                if hasattr(chunk, 'text'):
                    full_response += chunk.text
                    # 在文字後方加上游標符號 ▌
                    message_placeholder.markdown(full_response + "▌")
            
            # 回應結束，顯示完整文字 (移除游標)
            message_placeholder.markdown(full_response)
            
            # 3. 將 AI 的完整回應加入 session_state 紀錄
            st.session_state.messages.append({"role": "model", "content": full_response})
                
        except Exception as e:
            st.error(f"發生錯誤: {e}")
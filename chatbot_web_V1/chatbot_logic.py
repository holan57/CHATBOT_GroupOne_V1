import google.generativeai as genai
import google.api_core.exceptions
import os
import json
import threading
from typing import List, Dict, Callable

class GeminiChatService:
    """封裝與 Gemini API 的互動。"""
    def __init__(self, model_name: str = "gemini-1.5-flash"):
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("在 .env 檔案或環境變數中找不到 GOOGLE_API_KEY。")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name=model_name)
        self.chat = None

    def start_chat(self, history: List[Dict]):
        """根據提供的歷史紀錄開始一個新的聊天會話。"""
        self.chat = self.model.start_chat(history=history)

    def send_message(self, message: str, stream: bool = True):
        """傳送訊息到 Gemini API 並回傳回應。"""
        if not self.chat:
            raise RuntimeError("聊天會話尚未開始。請先呼叫 start_chat。")
        return self.chat.send_message(message, stream=stream)

    def get_history(self) -> List:
        """取得目前的對話歷史紀錄。"""
        return self.chat.history if self.chat else []

class ChatHistoryManager:
    """處理聊天紀錄的讀取和儲存。"""
    def __init__(self, history_file: str):
        self.history_file = history_file

    def load(self) -> List[Dict]:
        """從 JSON 檔案載入歷史紀錄。"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    history = json.load(f)
                print("成功載入先前的對話紀錄。")
                return history
        except (json.JSONDecodeError, FileNotFoundError):
            print("找不到或無法解析歷史紀錄檔案，將開始新的對話。")
        return []

    def save(self, history: List):
        """將歷史紀錄儲存到 JSON 檔案。"""
        if not history:
            return
        serializable_history = [
            {'role': msg.role, 'parts': [part.text for part in msg.parts]}
            for msg in history
        ]
        with open(self.history_file, 'w', encoding='utf-8') as f:
            json.dump(serializable_history, f, ensure_ascii=False, indent=4)
        print(f"對話紀錄已成功儲存至 {self.history_file}")

    def clear(self):
        """清除歷史紀錄檔案。"""
        with open(self.history_file, 'w', encoding='utf-8') as f:
            f.write("[]")

class ChatController:
    """協調 GUI、AI 服務和歷史紀錄管理。"""
    def __init__(self, gui, chat_service: GeminiChatService, history_manager: ChatHistoryManager):
        self.gui = gui
        self.chat_service = chat_service
        self.history_manager = history_manager

    def start_application(self):
        """初始化應用程式，載入歷史紀錄並開始聊天。"""
        history = self.history_manager.load()
        self.chat_service.start_chat(history=history)
        for msg in self.chat_service.get_history():
            role = "你" if msg.role == "user" else "AI"
            self.gui.display_message(f"{role}: {msg.parts[0].text}\n\n")

    def send_message(self, user_text: str):
        """處理傳送訊息的邏輯。"""
        self.gui.display_message(f"你: {user_text}\n\n")
        self.gui.set_input_state("disabled") # 改為字串，解除對 tk 的依賴
        self.gui.display_message("AI: 正在思考中...\n")

        def _get_response():
            try:
                response_stream = self.chat_service.send_message(user_text, stream=True)
                self.gui.stream_ai_response(response_stream)
            except google.api_core.exceptions.ResourceExhausted as e:
                self.gui.show_error("API 使用頻率過高，請稍後一分鐘再試...")
            except Exception as e:
                self.gui.show_error(f"發生錯誤：{e}")
            finally:
                self.gui.set_input_state("normal") # 改為字串

        threading.Thread(target=_get_response).start()

    def clear_history(self):
        """清除所有歷史紀錄。"""
        self.history_manager.clear()
        self.chat_service.start_chat(history=[])

    def on_closing(self):
        """處理關閉應用程式的邏輯。"""
        self.history_manager.save(self.chat_service.get_history())
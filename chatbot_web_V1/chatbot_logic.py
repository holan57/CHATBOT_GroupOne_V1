import google.generativeai as genai
import google.api_core.exceptions
import os
import json
import threading
from typing import List, Dict, Callable

class GeminiChatService:
    """
    封裝與 Google Gemini API 互動的邏輯。
    這個類別負責設定 API、開始聊天、傳送訊息和取得歷史紀錄。
    """
    def __init__(self, model_name: str = "gemini-1.5-flash", api_key: str = None):
        # 如果沒有傳入 api_key，嘗試從環境變數讀取
        if not api_key:
            api_key = os.getenv("GOOGLE_API_KEY")
            
        if not api_key:
            # 如果找不到 API Key，就拋出錯誤，提醒使用者設定
            raise ValueError("在 .env 檔案或環境變數中找不到 GOOGLE_API_KEY。")
        # 設定 genai 函式庫，讓它知道要用哪個金鑰
        genai.configure(api_key=api_key)
        # 根據指定的模型名稱，建立一個生成模型物件
        self.model = genai.GenerativeModel(model_name=model_name)
        # 初始化聊天會話為 None，等待 start_chat 被呼叫
        self.chat = None

    def start_chat(self, history: List[Dict]):
        """根據提供的歷史紀錄，開始一個新的或接續舊的聊天會話。"""
        # 使用模型物件和提供的歷史紀錄，開始一個聊天會話
        self.chat = self.model.start_chat(history=history)

    def send_message(self, message: str, stream: bool = True):
        """傳送訊息到 Gemini API 並回傳回應。"""
        if not self.chat:
            # 確保在傳送訊息前，聊天會話已經被初始化
            raise RuntimeError("聊天會話尚未開始。請先呼叫 start_chat。")
        # 將訊息傳送給 API。stream=True 表示要以串流方式逐字接收回應，
        # 這樣可以讓使用者感覺回應是即時的，而不是等全部生成完才顯示。
        return self.chat.send_message(message, stream=stream)

    def get_history(self) -> List:
        """取得目前的對話歷史紀錄。"""
        # 如果會話存在，回傳其歷史紀錄；否則回傳空列表
        return self.chat.history if self.chat else []

class ChatHistoryManager:
    """
    處理聊天紀錄的讀取和儲存。
    這個類別負責將對話紀錄從 JSON 檔案載入，以及將其儲存回 JSON 檔案。
    """
    def __init__(self, history_file: str):
        # 儲存歷史紀錄檔案的路徑
        self.history_file = history_file

    def load(self) -> List[Dict]:
        """從 JSON 檔案載入歷史紀錄。"""
        try:
            # 檢查歷史紀錄檔案是否存在
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    # 如果存在，就用 JSON 格式讀取內容
                    history = json.load(f)
                print("成功載入先前的對話紀錄。")
                return history
        except (json.JSONDecodeError, FileNotFoundError):
            # 如果檔案不存在，或檔案內容不是有效的 JSON，就印出提示並回傳空列表
            print("找不到或無法解析歷史紀錄檔案，將開始新的對話。")
        return []

    def save(self, history: List):
        """將歷史紀錄儲存到 JSON 檔案。"""
        if not history:
            # 如果歷史紀錄是空的，就沒什麼好存的，直接返回
            return
        # Gemini API 回傳的 history 物件 (Content) 不能直接存成 JSON。
        # 這裡需要手動將它轉換成一個可序列化的字典列表。
        serializable_history = [
            {'role': msg.role, 'parts': [part.text for part in msg.parts]}
            for msg in history
        ]
        with open(self.history_file, 'w', encoding='utf-8') as f:
            # 將轉換後的歷史紀錄寫入 JSON 檔案。
            # ensure_ascii=False 確保中文字能正常儲存，indent=4 讓 JSON 檔案格式更易讀。
            json.dump(serializable_history, f, ensure_ascii=False, indent=4)
        print(f"對話紀錄已成功儲存至 {self.history_file}")

    def clear(self):
        """清除歷史紀錄檔案。"""
        # 直接寫入一個空的 JSON 陣列來清空檔案內容
        with open(self.history_file, 'w', encoding='utf-8') as f:
            f.write("[]")

class ChatController:
    """
    協調器 (Controller)，作為使用者介面 (GUI)、AI 服務和歷史紀錄管理之間的橋樑。
    這是 Model-View-Controller (MVC) 設計模式的一種體現。
    """
    def __init__(self, gui, chat_service: GeminiChatService, history_manager: ChatHistoryManager):
        # 儲存各個元件的參考，以便後續呼叫它們的方法
        self.gui = gui
        self.chat_service = chat_service
        self.history_manager = history_manager

    def start_application(self):
        """初始化應用程式，載入歷史紀錄並開始聊天。"""
        # 1. 從檔案載入舊的對話紀錄
        history = self.history_manager.load()
        # 2. 用載入的紀錄初始化 AI 聊天會話
        self.chat_service.start_chat(history=history)
        # 3. 將舊的對話一條一條顯示在 GUI 上
        for msg in self.chat_service.get_history():
            role = "你" if msg.role == "user" else "AI"
            self.gui.display_message(f"{role}: {msg.parts[0].text}\n\n")

    def send_message(self, user_text: str):
        """處理傳送訊息的邏輯。"""
        # 1. 在 GUI 上顯示使用者剛輸入的訊息
        self.gui.display_message(f"你: {user_text}\n\n")
        # 2. 禁用輸入框，防止使用者在 AI 回應時重複傳送訊息
        self.gui.set_input_state("disabled") # 改為字串，解除對 tk 的依賴
        # 3. 顯示一個提示，讓使用者知道 AI 正在處理
        self.gui.display_message("AI: 正在思考中...\n")

        # 為了避免在等待 AI 回應時 GUI 介面卡住，我們將網路請求放在一個獨立的執行緒中執行
        def _get_response():
            try:
                # 呼叫 AI 服務傳送訊息，並取得回應的串流
                response_stream = self.chat_service.send_message(user_text, stream=True)
                # 將 AI 回應的串流傳給 GUI 處理，GUI 會逐塊更新介面以實現打字機效果
                self.gui.stream_ai_response(response_stream)
            except google.api_core.exceptions.ResourceExhausted as e:
                # 處理 API 超出用量限制的錯誤
                self.gui.show_error("API 使用頻率過高，請稍後一分鐘再試...")
            except Exception as e:
                # 處理其他所有可能的錯誤
                self.gui.show_error(f"發生錯誤：{e}")
            finally:
                # 不論成功或失敗，最後都要記得重新啟用輸入框
                self.gui.set_input_state("normal") # 改為字串

        # 建立並啟動一個新的執行緒來執行 _get_response 函式
        threading.Thread(target=_get_response).start()

    def clear_history(self):
        """清除所有歷史紀錄。"""
        # 1. 清除硬碟上的歷史紀錄檔案
        self.history_manager.clear()
        # 2. 重設 AI 服務中的聊天會話，開始一個全新的對話
        self.chat_service.start_chat(history=[])

    def on_closing(self):
        """處理關閉應用程式的邏輯。"""
        # 在程式關閉前，將目前的對話紀錄儲存到檔案中，以便下次開啟時能接續
        self.history_manager.save(self.chat_service.get_history())
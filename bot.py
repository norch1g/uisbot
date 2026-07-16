import requests
import threading
import time
import os
import sys
import configparser
import socket
import json
import subprocess
from flask import Flask, request
from datetime import datetime
import customtkinter as ctk

# ===== НАСТРОЙКИ GUI =====
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

DARK_BG = "#1a1a1a"
DARKER_BG = "#0d0d0d"
GREEN_ACCENT = "#00ff00"
GREEN_DARK = "#00cc00"
RED_ACCENT = "#ff3333"
TEXT_COLOR = "#ffffff"
TEXT_MUTED = "#888888"

# ===== КОНФИГ =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
CONFIG_FILE = os.path.join(BASE_DIR, "settings.ini")
LOGS_DIR = os.path.join(BASE_DIR, "logs")

if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

def create_default_config():
    if not os.path.exists(CONFIG_FILE):
        config = configparser.ConfigParser()
        config["SETTINGS"] = {
            "tg_token": "YOUR_TELEGRAM_BOT_TOKEN"
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            config.write(f)
        return True
    return False


def open_path(path):
    """Cross-platform 'open file with default app' (replaces Windows-only os.startfile)."""
    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass

create_default_config()

# ===== ГЛОБАЛЬНЫЕ ПЕРЕМЕННЫЕ =====
active = False
subscribed_users = {}
UIS_PORT = 5000

# ===== FLASK =====
flask_app = Flask(__name__)
gui_instance = None

@flask_app.route('/uis', methods=['POST', 'GET'])
def uis_webhook():
    try:
        raw_data = request.get_data(as_text=True)
        
        if gui_instance:
            gui_instance.add_log(f"📥 RAW: {raw_data[:300]}")
        
        data = {}
        
        if raw_data and raw_data.strip():
            fixed_data = raw_data.replace('""', '"')
            
            try:
                data = json.loads(fixed_data)
            except:
                try:
                    data = json.loads(raw_data)
                except:
                    if request.form:
                        data = dict(request.form)
                    else:
                        data = {}
        
        if not data:
            return "OK", 200
        
        campaign_name = data.get('campaign_name', '')
        notification_name = data.get('notification_name', data.get('name', 'Уведомление UIS'))
        notification_time = data.get('notification_time', data.get('time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        virtual_phone_number = data.get('virtual_phone_number', data.get('virtual_number', 'Неизвестно'))
        contact_phone_number = data.get('contact_phone_number', data.get('contact_number', data.get('phone', 'Неизвестно')))
        talk_time_duration = data.get('talk_time_duration', data.get('wait_time_duration', data.get('duration', '0')))
        
        if campaign_name:
            message = f"🔔 Уведомление UIS:\n\n{campaign_name}\n"
        else:
            message = "🔔 Уведомление UIS:\n\n"
        
        message += f'"{notification_name}". \n'
        message += f"Время наступления события: {notification_time}\n"
        message += f"виртуальный номер: {virtual_phone_number}, \n"
        message += f"номер с которого поступил вызов: {contact_phone_number}"
        
        if talk_time_duration and talk_time_duration != '0' and talk_time_duration != '{{talk_time_duration}}':
            message += f"\nдлительность разговора: {talk_time_duration}с"
        
        if gui_instance:
            gui_instance.notify_subscribers(message)
        
        return "OK", 200
        
    except Exception as e:
        if gui_instance:
            gui_instance.add_log(f"❌ Ошибка: {str(e)}")
        return "OK", 200

@flask_app.route('/test', methods=['GET'])
def test_endpoint():
    return "UIS Webhook server is running!", 200

# ===== GUI ПРИЛОЖЕНИЕ =====
class UISControlCenter(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        global gui_instance
        gui_instance = self
        
        self.title("UIS Control Center")
        self.geometry("900x650")
        self.minsize(700, 500)
        self.configure(fg_color=DARK_BG)
        
        self.conf = self.load_config()
        self.active = False
        
        self.load_subscribed()
        self.setup_ui()
        self.check_config()
        
    def load_config(self):
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE, encoding="utf-8")
            return config["SETTINGS"] if "SETTINGS" in config else {}
        return {}
    
    def check_config(self):
        tg_token = self.conf.get('tg_token', '')

        if not tg_token or tg_token == "YOUR_TELEGRAM_BOT_TOKEN":
            self.add_log("⚠️ Токен не настроен!")
        else:
            self.add_log("✅ Токен найден")
            self.test_connection()

    def test_connection(self):
        try:
            r = requests.get(
                f"https://api.telegram.org/bot{self.conf['tg_token']}/getMe",
                timeout=15
            )
            if r.status_code == 200 and r.json().get("ok"):
                bot_info = r.json()["result"]
                self.add_log(f"✅ Подключено как @{bot_info.get('username', '?')}")
            else:
                self.add_log(f"⚠️ Telegram API вернул код {r.status_code}")
        except Exception as e:
            self.add_log(f"❌ Не удалось подключиться к Telegram: {str(e)[:80]}")
    
    def load_subscribed(self):
        global subscribed_users
        sub_file = os.path.join(LOGS_DIR, "subscribed.json")
        if os.path.exists(sub_file):
            try:
                with open(sub_file, "r", encoding="utf-8") as f:
                    subscribed_users = json.load(f)
            except:
                subscribed_users = {}
        else:
            subscribed_users = {}
    
    def save_subscribed(self):
        with open(os.path.join(LOGS_DIR, "subscribed.json"), "w", encoding="utf-8") as f:
            json.dump(subscribed_users, f, ensure_ascii=False, indent=2)
        
        with open(os.path.join(LOGS_DIR, "subscribed.txt"), "w", encoding="utf-8") as f:
            f.write("=" * 60 + "\n")
            f.write(f"СПИСОК ПОДПИСЧИКОВ ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')})\n")
            f.write("=" * 60 + "\n\n")
            
            for i, (chat_id, info) in enumerate(subscribed_users.items(), 1):
                username = info.get('username', '')
                first_name = info.get('first_name', '')
                last_name = info.get('last_name', '')
                date = info.get('date', '')
                
                f.write(f"{i}. Chat ID: {chat_id}\n")
                if username:
                    f.write(f"   Username: @{username}\n")
                if first_name:
                    f.write(f"   Имя: {first_name}\n")
                if last_name:
                    f.write(f"   Фамилия: {last_name}\n")
                if date:
                    f.write(f"   Дата подписки: {date}\n")
                f.write("\n")
            
            f.write("=" * 60 + "\n")
            f.write(f"Всего подписчиков: {len(subscribed_users)}\n")
    
    def setup_ui(self):
        top_frame = ctk.CTkFrame(self, fg_color=DARKER_BG, height=60, corner_radius=0)
        top_frame.pack(fill="x", side="top")
        top_frame.pack_propagate(False)
        
        ctk.CTkLabel(top_frame, text="UIS CONTROL CENTER", font=("Arial", 20, "bold"), text_color=GREEN_ACCENT).pack(side="left", padx=20, pady=15)
        
        self.status_frame = ctk.CTkFrame(top_frame, fg_color="transparent")
        self.status_frame.pack(side="right", padx=20, pady=15)
        
        self.status_indicator = ctk.CTkLabel(self.status_frame, text="⚫", font=("Arial", 16), text_color=RED_ACCENT)
        self.status_indicator.pack(side="left", padx=5)
        
        self.status_label = ctk.CTkLabel(self.status_frame, text="ОСТАНОВЛЕН", font=("Arial", 12, "bold"), text_color=TEXT_MUTED)
        self.status_label.pack(side="left")
        
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        left_panel = ctk.CTkFrame(main_frame, fg_color=DARKER_BG, width=280, corner_radius=10)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.pack_propagate(False)
        
        ctk.CTkLabel(left_panel, text="СТАТИСТИКА", font=("Arial", 14, "bold"), text_color=GREEN_ACCENT).pack(pady=(20, 15))
        
        self.subs_label = ctk.CTkLabel(left_panel, text=f"Подписчиков: {len(subscribed_users)}", font=("Arial", 12), text_color=TEXT_COLOR)
        self.subs_label.pack(pady=5)
        
        self.port_label = ctk.CTkLabel(left_panel, text=f"HTTP порт: {UIS_PORT}", font=("Arial", 12), text_color=TEXT_COLOR)
        self.port_label.pack(pady=5)
        
        ctk.CTkFrame(left_panel, height=2, fg_color=GREEN_DARK).pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(left_panel, text="УПРАВЛЕНИЕ", font=("Arial", 14, "bold"), text_color=GREEN_ACCENT).pack(pady=(0, 15))
        
        self.start_btn = ctk.CTkButton(left_panel, text="▶ ЗАПУСТИТЬ", font=("Arial", 14, "bold"), fg_color=GREEN_DARK, hover_color="#009900", height=45, command=self.start_bot)
        self.start_btn.pack(padx=20, pady=5)
        
        self.stop_btn = ctk.CTkButton(left_panel, text="⏹ ОСТАНОВИТЬ", font=("Arial", 14, "bold"), fg_color=RED_ACCENT, hover_color="#cc0000", height=45, state="disabled", command=self.stop_bot)
        self.stop_btn.pack(padx=20, pady=5)
        
        ctk.CTkFrame(left_panel, height=2, fg_color=GREEN_DARK).pack(fill="x", padx=20, pady=20)
        
        ctk.CTkLabel(left_panel, text="URL ДЛЯ UIS:", font=("Arial", 11), text_color=TEXT_MUTED).pack()
        
        self.url_text = ctk.CTkTextbox(left_panel, height=50, font=("Consolas", 10), fg_color=DARK_BG, text_color=GREEN_ACCENT, wrap="word")
        self.url_text.pack(padx=20, pady=5, fill="x")
        
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except:
            local_ip = "127.0.0.1"
        
        self.url_text.insert("1.0", f"http://{local_ip}:{UIS_PORT}/uis")
        self.url_text.configure(state="disabled")
        
        ctk.CTkButton(left_panel, text="📁 Открыть settings.ini", font=("Arial", 11), fg_color="#333333", hover_color="#444444", height=35, command=self.open_config).pack(padx=20, pady=(10, 5))
        ctk.CTkButton(left_panel, text="📄 Список подписчиков", font=("Arial", 11), fg_color="#333333", hover_color="#444444", height=35, command=self.open_subscribers_file).pack(padx=20, pady=5)
        
        right_panel = ctk.CTkFrame(main_frame, fg_color=DARKER_BG, corner_radius=10)
        right_panel.pack(side="right", fill="both", expand=True)
        
        ctk.CTkLabel(right_panel, text="ЛОГИ СОБЫТИЙ", font=("Arial", 14, "bold"), text_color=GREEN_ACCENT).pack(pady=(20, 10))
        
        self.logs_text = ctk.CTkTextbox(right_panel, font=("Consolas", 11), fg_color=DARK_BG, text_color=TEXT_COLOR, wrap="word")
        self.logs_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        self.add_log("🟢 UIS Control Center запущен")
        self.add_log(f"🌐 HTTP сервер на порту {UIS_PORT}")
    
    def open_config(self):
        if os.path.exists(CONFIG_FILE):
            open_path(CONFIG_FILE)
    
    def open_subscribers_file(self):
        sub_file = os.path.join(LOGS_DIR, "subscribed.txt")
        self.save_subscribed()
        if os.path.exists(sub_file):
            open_path(sub_file)
    
    def add_log(self, message):
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted = f"[{timestamp}] {message}\n"
        self.logs_text.insert("end", formatted)
        self.logs_text.see("end")
    
    def start_bot(self):
        global active
        if active:
            return
        
        active = True
        self.active = True
        
        self.status_indicator.configure(text="🟢", text_color=GREEN_ACCENT)
        self.status_label.configure(text="РАБОТАЕТ", text_color=GREEN_ACCENT)
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        
        self.add_log("🟢 СИСТЕМА ЗАПУЩЕНА")
        
        threading.Thread(target=lambda: flask_app.run(host='0.0.0.0', port=UIS_PORT, debug=False, use_reloader=False), daemon=True).start()
        time.sleep(1)
        
        threading.Thread(target=self.listen_tg, daemon=True).start()
    
    def stop_bot(self):
        global active
        active = False
        self.active = False
        
        self.status_indicator.configure(text="⚫", text_color=RED_ACCENT)
        self.status_label.configure(text="ОСТАНОВЛЕН", text_color=TEXT_MUTED)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        
        self.add_log("🔴 СИСТЕМА ОСТАНОВЛЕНА")
    
    def update_stats(self):
        self.subs_label.configure(text=f"Подписчиков: {len(subscribed_users)}")
    
    def notify_subscribers(self, message):
        if not self.conf.get('tg_token') or self.conf['tg_token'] == "YOUR_TELEGRAM_BOT_TOKEN":
            return

        for cid in subscribed_users:
            try:
                url = f"https://api.telegram.org/bot{self.conf['tg_token']}/sendMessage"
                requests.post(url, json={"chat_id": cid, "text": message}, timeout=15)
            except:
                pass
    
    def tg_send(self, cid, text):
        if not self.conf.get('tg_token'):
            return False
        try:
            url = f"https://api.telegram.org/bot{self.conf['tg_token']}/sendMessage"
            r = requests.post(url, json={"chat_id": cid, "text": text}, timeout=15)
            return r.status_code == 200
        except:
            return False
    
    def listen_tg(self):
        if not self.conf.get('tg_token') or self.conf['tg_token'] == "YOUR_TELEGRAM_BOT_TOKEN":
            return

        off = 0
        
        self.add_log("📡 Слушатель запущен")
        
        while active:
            try:
                url = f"https://api.telegram.org/bot{self.conf['tg_token']}/getUpdates"
                r = requests.get(url, params={"offset": off, "timeout": 30}, timeout=35)
                
                if r.status_code != 200:
                    time.sleep(5)
                    continue
                
                data = r.json()
                if not data.get("ok"):
                    time.sleep(5)
                    continue
                
                for u in data.get("result", []):
                    m = u.get("message")
                    if not m:
                        continue
                    
                    cid = str(m["chat"]["id"])
                    user = m["from"]
                    txt = m.get("text", "").strip()
                    
                    if txt == "/start":
                        subscribed_users[cid] = {
                            "username": user.get("username", ""),
                            "first_name": user.get("first_name", ""),
                            "last_name": user.get("last_name", ""),
                            "date": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        }
                        self.save_subscribed()
                        self.tg_send(cid, "✅ Вы подписаны на уведомления!")
                        self.update_stats()
                    
                    off = u["update_id"] + 1
            except Exception as e:
                if active:
                    time.sleep(5)

if __name__ == "__main__":
    app = UISControlCenter()
    app.mainloop()
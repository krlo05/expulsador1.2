import sqlite3
import datetime
import asyncio
import os
import requests
import threading
from flask import Flask
from telegram import Update, ChatMember
from telegram.ext import (
    ApplicationBuilder,
    ChatMemberHandler,
    ContextTypes,
)

# 🔐 Token y constantes
TOKEN = '7725370274:AAG8f63RCrHd1PCcV4hpupwuQ3if-9RPI-I'
DB_NAME = 'members.db'
RENDER_URL = 'https://telegram-expulsador-bot.onrender.com'
ADMIN_CHAT_ID = 5286685895  # Coloca tu chat ID de Telegram para pruebas

# 🌐 Flask app para keep-alive (por ejemplo en Render)
app_web = Flask(__name__)

@app_web.route('/')
def index():
    return 'Bot funcionando correctamente ✅'

# 🧱 Inicializar DB
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            user_id INTEGER,
            chat_id INTEGER,
            join_date TEXT,
            PRIMARY KEY (user_id, chat_id)
        )
    ''')
    conn.commit()
    conn.close()

# 📥 Manejo de usuarios que se unen
async def handle_chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    member_update = update.chat_member
    if member_update.new_chat_member.status == ChatMember.MEMBER:
        user = member_update.from_user
        user_id = user.id
        username = user.username or f"id:{user_id}"
        chat_id = member_update.chat.id
        join_date = datetime.datetime.now(datetime.timezone.utc).isoformat()

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO members (user_id, chat_id, join_date)
            VALUES (?, ?, ?)
        ''', (user_id, chat_id, join_date))
        conn.commit()
        conn.close()

        print(f"📥 Usuario nuevo: @{username} agregado el {join_date}")

# 🚫 Expulsión de usuarios luego de cierto tiempo
async def check_old_members(app):
    while True:
        now = datetime.datetime.now(datetime.timezone.utc)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT user_id, chat_id, join_date FROM members')
        rows = cursor.fetchall()

        for user_id, chat_id, join_date in rows:
            joined = datetime.datetime.fromisoformat(join_date)
            seconds_in_group = (now - joined).total_seconds()
            print(f"⏳ Usuario {user_id} lleva {seconds_in_group:.1f} segundos en el grupo")

            if seconds_in_group >= 120:
                try:
                    await app.bot.ban_chat_member(chat_id, user_id)
                    await app.bot.unban_chat_member(chat_id, user_id)
                    print(f"🧼 Usuario {user_id} expulsado del grupo {chat_id}")
                    cursor.execute('DELETE FROM members WHERE user_id = ? AND chat_id = ?', (user_id, chat_id))
                    conn.commit()
                except Exception as e:
                    print(f"⚠️ Error expulsando a {user_id}: {e}")
        conn.close()
        await asyncio.sleep(30)

# 🔄 Keep-alive para Render u otro hosting
async def keep_alive():
    while True:
        try:
            requests.get(RENDER_URL)
            print("🔄 Ping enviado a Render")
        except Exception as e:
            print(f"⚠️ Error enviando ping a Render: {e}")
        await asyncio.sleep(600)

# 🧠 Función principal del bot
async def bot_main():
    init_db()

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(ChatMemberHandler(handle_chat_member_update, ChatMemberHandler.CHAT_MEMBER))

    # Tareas paralelas
    asyncio.create_task(check_old_members(app))
    asyncio.create_task(keep_alive())

    print("🤖 Bot corriendo...")

    try:
        await app.bot.send_message(chat_id=ADMIN_CHAT_ID, text="🤖 Bot iniciado correctamente y en funcionamiento ✅")
    except Exception as e:
        print(f"⚠️ No se pudo enviar mensaje al admin: {e}")

    await app.run_polling()

# 🚀 Iniciar bot y servidor web sin conflictos de event loop
if __name__ == '__main__':
    threading.Thread(target=lambda: app_web.run(host='0.0.0.0', port=10000), daemon=True).start()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(bot_main())
    loop.run_forever()


# -*- coding: utf-8 -*-
import telebot
import os
import random
import sqlite3
import time
from datetime import datetime, timedelta
import threading
import schedule

# ========== НАСТРОЙКИ ==========
# Берём токен из переменных окружения Railway
TOKEN = os.environ.get('BOT_TOKEN', "8514983133:AAF4dvNmweMg8LOBVB2evu_bw3td3d_p8jM")
bot = telebot.TeleBot(TOKEN)

# Создаём папки для фото
os.makedirs("images/real", exist_ok=True)
os.makedirs("images/ai", exist_ok=True)
os.makedirs("images/suggested", exist_ok=True)

# Словарь для текущих игр
current_games = {}

# ========== ДОСТИЖЕНИЯ ==========
ACHIEVEMENTS = {
    'newbie': {'name': '🌱 Новичок', 'desc': 'Сыграть 10 игр', 'icon': '🌱', 'target': 10},
    'player': {'name': '⭐ Игрок', 'desc': 'Сыграть 50 игр', 'icon': '⭐', 'target': 50},
    'pro': {'name': '🏆 Профи', 'desc': 'Сыграть 100 игр', 'icon': '🏆', 'target': 100},
    'veteran': {'name': '⚡ Ветеран', 'desc': 'Сыграть 500 игр', 'icon': '⚡', 'target': 500},
    'streak_10': {'name': '🔥 Серия 10', 'desc': '10 побед подряд', 'icon': '🔥', 'target': 10},
    'streak_25': {'name': '⚡ Серия 25', 'desc': '25 побед подряд', 'icon': '⚡', 'target': 25},
    'streak_50': {'name': '💫 Серия 50', 'desc': '50 побед подряд', 'icon': '💫', 'target': 50},
    'ai_hunter': {'name': '🤖 Охотник на ИИ', 'desc': 'Угадать 50 ИИ', 'icon': '🤖', 'target': 50},
    'ai_master': {'name': '🎓 Мастер ИИ', 'desc': 'Угадать 200 ИИ', 'icon': '🎓', 'target': 200},
    'ai_legend': {'name': '👑 Легенда ИИ', 'desc': 'Угадать 500 ИИ', 'icon': '👑', 'target': 500},
    'photo_master': {'name': '📸 Мастер фото', 'desc': 'Угадать 50 фото', 'icon': '📸', 'target': 50},
    'photo_legend': {'name': '👑 Легенда фото', 'desc': 'Угадать 200 фото', 'icon': '👑', 'target': 200},
    'contributor': {'name': '📤 Контрибьютор', 'desc': 'Предложить 5 фото', 'icon': '📤', 'target': 5},
    'curator': {'name': '🎨 Куратор', 'desc': 'Предложить 20 фото', 'icon': '🎨', 'target': 20},
    'daily_7': {'name': '📅 Неделя', 'desc': '7 челленджей', 'icon': '📅', 'target': 7},
    'daily_30': {'name': '📅 Месяц', 'desc': '30 челленджей', 'icon': '📅', 'target': 30},
}

# ========== БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        score INTEGER DEFAULT 0,
        games INTEGER DEFAULT 0,
        correct INTEGER DEFAULT 0,
        ai_correct INTEGER DEFAULT 0,
        real_correct INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        max_streak INTEGER DEFAULT 0,
        achievements TEXT DEFAULT '',
        contributed INTEGER DEFAULT 0,
        daily_done TEXT DEFAULT '',
        last_daily TEXT
    )
    ''')
    
    # Таблица изображений
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        label TEXT,
        filename TEXT,
        category TEXT DEFAULT 'other',
        times_used INTEGER DEFAULT 0,
        correct_count INTEGER DEFAULT 0
    )
    ''')
    
    # Таблица истории
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        image_id INTEGER,
        is_correct INTEGER,
        response_time REAL,
        timestamp TEXT
    )
    ''')
    
    # Таблица предложенных фото
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        file_path TEXT,
        label TEXT,
        timestamp TEXT,
        approved INTEGER DEFAULT 0
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ База данных создана")

def load_images():
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM images")
    if cursor.fetchone()[0] == 0:
        print("📸 Загружаем изображения...")
        
        # Реальные фото
        if os.path.exists("images/real"):
            for f in os.listdir("images/real"):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    path = os.path.join("images/real", f)
                    cursor.execute("INSERT INTO images (file_path, label, filename) VALUES (?, ?, ?)",
                                 (path, 'real', f))
        
        # ИИ-фото
        if os.path.exists("images/ai"):
            for f in os.listdir("images/ai"):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    path = os.path.join("images/ai", f)
                    cursor.execute("INSERT INTO images (file_path, label, filename) VALUES (?, ?, ?)",
                                 (path, 'ai', f))
        
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM images")
        total = cursor.fetchone()[0]
        print(f"✅ Загружено {total} изображений")
    
    conn.close()

def get_random_image():
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_path, label FROM images ORDER BY RANDOM() LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    return result

def update_user_stats(user_id, username, image_id, guess, correct_label, response_time):
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    
    is_correct = (guess == correct_label)
    points = 10 if is_correct else -5
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if user:
        new_score = user[2] + points
        new_games = user[3] + 1
        new_correct = user[4] + (1 if is_correct else 0)
        
        ai_correct = user[5] + (1 if is_correct and correct_label == 'ai' else 0)
        real_correct = user[6] + (1 if is_correct and correct_label == 'real' else 0)
        
        new_streak = user[7] + 1 if is_correct else 0
        new_max_streak = max(user[8], new_streak)
        
        cursor.execute('''
            UPDATE users 
            SET score=?, games=?, correct=?, ai_correct=?, real_correct=?,
                streak=?, max_streak=?
            WHERE user_id=?
        ''', (new_score, new_games, new_correct, ai_correct, real_correct,
              new_streak, new_max_streak, user_id))
    else:
        cursor.execute('''
            INSERT INTO users 
            (user_id, username, score, games, correct, ai_correct, real_correct, streak, max_streak)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_id, username, 
            points, 1, 1 if is_correct else 0,
            1 if is_correct and correct_label == 'ai' else 0,
            1 if is_correct and correct_label == 'real' else 0,
            1 if is_correct else 0,
            1 if is_correct else 0
        ))
    
    cursor.execute('''
        INSERT INTO history (user_id, image_id, is_correct, response_time, timestamp)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, image_id, 1 if is_correct else 0, response_time,
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    cursor.execute('''
        UPDATE images SET times_used = times_used + 1,
        correct_count = correct_count + ? WHERE id = ?
    ''', (1 if is_correct else 0, image_id))
    
    conn.commit()
    conn.close()
    
    return is_correct, points, new_streak if user else (1 if is_correct else 0)

def get_user_stats(user_id):
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT score, games, correct, ai_correct, real_correct, 
               streak, max_streak, achievements, contributed
        FROM users WHERE user_id=?
    ''', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result:
        score, games, correct, ai_correct, real_correct, streak, max_streak, achievements, contributed = result
        accuracy = round((correct / games) * 100, 1) if games > 0 else 0
        return {
            'score': score,
            'games': games,
            'correct': correct,
            'ai_correct': ai_correct,
            'real_correct': real_correct,
            'streak': streak,
            'max_streak': max_streak,
            'accuracy': accuracy,
            'achievements': achievements.split(',') if achievements else [],
            'contributed': contributed
        }
    return None

def check_achievements(user_id):
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT games, correct, ai_correct, real_correct, streak, achievements, contributed
        FROM users WHERE user_id=?
    ''', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return []
    
    games, correct, ai_correct, real_correct, streak, achievements_str, contributed = user
    current = achievements_str.split(',') if achievements_str else []
    new = []
    
    checks = [
        ('newbie', games >= 10),
        ('player', games >= 50),
        ('pro', games >= 100),
        ('veteran', games >= 500),
        ('streak_10', streak >= 10),
        ('streak_25', streak >= 25),
        ('streak_50', streak >= 50),
        ('ai_hunter', ai_correct >= 50),
        ('ai_master', ai_correct >= 200),
        ('ai_legend', ai_correct >= 500),
        ('photo_master', real_correct >= 50),
        ('photo_legend', real_correct >= 200),
        ('contributor', contributed >= 5),
        ('curator', contributed >= 20),
    ]
    
    for ach_id, condition in checks:
        if ach_id not in current and condition:
            new.append(ach_id)
    
    if new:
        all_achievements = current + new
        cursor.execute("UPDATE users SET achievements=? WHERE user_id=?", (','.join(all_achievements), user_id))
        conn.commit()
    
    conn.close()
    return new

def get_top_users(limit=10):
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT username, score, games, correct, streak 
        FROM users 
        WHERE games > 0 
        ORDER BY score DESC 
        LIMIT ?
    ''', (limit,))
    users = cursor.fetchall()
    conn.close()
    return users

def check_daily_challenge(user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    cursor.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0] == today:
        conn.close()
        return False
    
    cursor.execute("UPDATE users SET last_daily=? WHERE user_id=?", (today, user_id))
    
    cursor.execute("SELECT daily_done FROM users WHERE user_id=?", (user_id,))
    daily_count = cursor.fetchone()
    if daily_count and daily_count[0]:
        daily_list = daily_count[0].split(',')
        if today not in daily_list:
            new_daily = daily_count[0] + today + ','
            cursor.execute("UPDATE users SET daily_done=? WHERE user_id=?", (new_daily, user_id))
    else:
        cursor.execute("UPDATE users SET daily_done=? WHERE user_id=?", (today + ',', user_id))
    
    conn.commit()
    conn.close()
    return True

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        telebot.types.KeyboardButton("🎮 ИГРАТЬ"),
        telebot.types.KeyboardButton("📊 СТАТИСТИКА"),
        telebot.types.KeyboardButton("🏆 РЕЙТИНГ"),
        telebot.types.KeyboardButton("🎯 БОНУСЫ"),
        telebot.types.KeyboardButton("📤 ПРЕДЛОЖИТЬ"),
        telebot.types.KeyboardButton("❓ ПОМОЩЬ")
    )
    return keyboard

def get_bonus_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        telebot.types.KeyboardButton("🏅 ДОСТИЖЕНИЯ"),
        telebot.types.KeyboardButton("📈 ПРОГРЕСС"),
        telebot.types.KeyboardButton("📅 ЧЕЛЛЕНДЖ"),
        telebot.types.KeyboardButton("🔙 НАЗАД")
    )
    return keyboard

# ========== КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "👋 **Привет! Я ИИ-Детектив!**\n\n"
        "Я покажу тебе фото, а ты угадай:\n"
        "📸 Это **реальное** фото или 🤖 **создано ИИ**?\n\n"
        "👇 **Выбирай кнопку ниже!**",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "🎮 ИГРАТЬ")
def play(message):
    image = get_random_image()
    
    if not image:
        bot.reply_to(
            message,
            "😕 Пока нет фото в базе. Попробуй позже!",
            reply_markup=get_main_keyboard()
        )
        return
    
    image_id, file_path, correct_label = image
    
    current_games[message.chat.id] = {
        'image_id': image_id,
        'correct': correct_label,
        'start_time': time.time()
    }
    
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(
        telebot.types.InlineKeyboardButton("📸 РЕАЛЬНОЕ", callback_data=f"real_{image_id}"),
        telebot.types.InlineKeyboardButton("🤖 ИИ", callback_data=f"ai_{image_id}")
    )
    
    try:
        with open(file_path, 'rb') as photo:
            bot.send_photo(
                message.chat.id,
                photo,
                caption="👇 **Как думаешь?**",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
    except Exception as e:
        bot.reply_to(message, f"😕 Ошибка загрузки фото: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('real_', 'ai_')))
def handle_answer(call):
    data = call.data.split('_')
    guess = data[0]
    image_id = int(data[1])
    user_id = call.from_user.id
    username = call.from_user.username or f"user_{user_id}"
    
    # Проверяем ежедневный челлендж
    is_daily = check_daily_challenge(user_id)
    
    # Получаем правильный ответ
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    cursor.execute("SELECT label FROM images WHERE id = ?", (image_id,))
    correct = cursor.fetchone()[0]
    conn.close()
    
    # Время ответа
    game_data = current_games.get(call.message.chat.id, {})
    start_time = game_data.get('start_time', time.time())
    response_time = time.time() - start_time
    
    # Обновляем статистику
    is_correct, points, streak = update_user_stats(
        user_id, username, image_id, guess, correct, response_time
    )
    
    # Проверяем достижения
    new_achievements = check_achievements(user_id)
    
    # Получаем статистику
    stats = get_user_stats(user_id)
    
    # Формируем результат
    if is_correct:
        result = "✅ **ПРАВИЛЬНО!**"
    else:
        correct_word = "📸 РЕАЛЬНОЕ" if correct == 'real' else "🤖 ИИ"
        result = f"❌ **НЕ УГАДАЛ...**\nПравильно: {correct_word}"
    
    result += f"\n💰 {points} очков | ⏱ {response_time:.1f} сек\n\n"
    result += f"📊 **Твоя статистика:**\n"
    result += f"• 🏆 Очки: {stats['score']}\n"
    result += f"• 🎮 Игр: {stats['games']}\n"
    result += f"• 🔥 Серия: {stats['streak']} (рекорд: {stats['max_streak']})\n"
    result += f"• 📈 Точность: {stats['accuracy']}%\n\n"
    
    if new_achievements:
        result += "🏅 **Новые достижения!**\n"
        for ach in new_achievements:
            result += f"• {ACHIEVEMENTS[ach]['icon']} {ACHIEVEMENTS[ach]['name']}\n"
    
    bot.send_message(user_id, result, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    
    # Убираем кнопки
    bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=None
    )
    
    if call.message.chat.id in current_games:
        del current_games[call.message.chat.id]

@bot.message_handler(func=lambda msg: msg.text == "📊 СТАТИСТИКА")
def show_stats(message):
    stats = get_user_stats(message.from_user.id)
    
    if not stats or stats['games'] == 0:
        bot.reply_to(
            message,
            "😕 Ты ещё не играл!\n\nЖми 🎮 ИГРАТЬ!",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = f"📊 **Твоя статистика**\n\n"
    text += f"🎮 Игр: {stats['games']}\n"
    text += f"✅ Правильно: {stats['correct']}\n"
    text += f"❌ Ошибок: {stats['games'] - stats['correct']}\n"
    text += f"📈 Точность: {stats['accuracy']}%\n"
    text += f"🏆 Очки: {stats['score']}\n\n"
    text += f"🤖 Угадано ИИ: {stats['ai_correct']}\n"
    text += f"📸 Угадано фото: {stats['real_correct']}\n"
    text += f"🔥 Серия: {stats['streak']} (рекорд: {stats['max_streak']})\n"
    text += f"📤 Предложено фото: {stats['contributed']}\n\n"
    
    if stats['achievements']:
        text += "🏅 **Достижения:**\n"
        for ach in stats['achievements'][:6]:
            if ach in ACHIEVEMENTS:
                text += f"• {ACHIEVEMENTS[ach]['icon']} {ACHIEVEMENTS[ach]['name']}\n"
    
    bot.reply_to(message, text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🏆 РЕЙТИНГ")
def show_top(message):
    users = get_top_users()
    
    if not users:
        bot.reply_to(
            message,
            "🏆 Рейтинг пуст!\n\nБудь первым!",
            reply_markup=get_main_keyboard()
        )
        return
    
    text = "🏆 **ТОП-10 ИГРОКОВ**\n\n"
    for i, (username, score, games, correct, streak) in enumerate(users, 1):
        name = username or f"Игрок{i}"
        accuracy = round((correct / games) * 100, 1) if games > 0 else 0
        
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} {name}\n"
        text += f"   ├ 🏆 {score} очков\n"
        text += f"   └ 📈 {accuracy}% | 🔥 {streak}\n"
    
    bot.reply_to(message, text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🎯 БОНУСЫ")
def bonus_menu(message):
    bot.reply_to(
        message,
        "🎯 **Бонусы и достижения**\n\n"
        "Выбери, что хочешь посмотреть:",
        reply_markup=get_bonus_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "🏅 ДОСТИЖЕНИЯ")
def show_achievements(message):
    stats = get_user_stats(message.from_user.id)
    
    if not stats:
        bot.reply_to(
            message,
            "😕 Сначала поиграй!",
            reply_markup=get_bonus_keyboard()
        )
        return
    
    text = "🏅 **Все достижения**\n\n"
    
    for ach_id, ach in ACHIEVEMENTS.items():
        if ach_id in stats['achievements']:
            text += f"✅ {ach['icon']} {ach['name']}\n"
        else:
            text += f"⬜ {ach['icon']} {ach['name']}\n"
    
    bot.reply_to(message, text, reply_markup=get_bonus_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📈 ПРОГРЕСС")
def show_progress(message):
    stats = get_user_stats(message.from_user.id)
    
    if not stats or stats['games'] < 5:
        bot.reply_to(
            message,
            "😕 Нужно больше игр для графика (минимум 5)!",
            reply_markup=get_bonus_keyboard()
        )
        return
    
    # Простая текстовая статистика вместо графика
    text = f"📈 **Твой прогресс**\n\n"
    text += f"📊 Всего игр: {stats['games']}\n"
    text += f"✅ Точность: {stats['accuracy']}%\n"
    text += f"🔥 Лучшая серия: {stats['max_streak']}\n"
    text += f"🎯 Угадано ИИ: {stats['ai_correct']}\n"
    text += f"📸 Угадано фото: {stats['real_correct']}\n\n"
    text += f"Продолжай в том же духе! 💪"
    
    bot.reply_to(message, text, reply_markup=get_bonus_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "📅 ЧЕЛЛЕНДЖ")
def daily_challenge(message):
    is_new = check_daily_challenge(message.from_user.id)
    
    if is_new:
        bot.reply_to(
            message,
            "📅 **Ежедневный челлендж!**\n\n"
            "Сегодня за каждую игру ты получаешь:\n"
            "• ✅ Правильно: **+20 очков** (вместо 10)\n"
            "• ❌ Ошибка: **-5 очков**\n\n"
            "👉 Жми 🎮 ИГРАТЬ!",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )
    else:
        bot.reply_to(
            message,
            "✅ **Ты уже сегодня играл!**\n\n"
            "Возвращайся завтра за новым бонусом!",
            reply_markup=get_main_keyboard(),
            parse_mode="Markdown"
        )

@bot.message_handler(func=lambda msg: msg.text == "📤 ПРЕДЛОЖИТЬ")
def suggest_photo(message):
    bot.reply_to(
        message,
        "📤 **Предложить фото**\n\n"
        "Хочешь добавить своё фото в игру?\n\n"
        "1️⃣ Отправь мне фото\n"
        "2️⃣ В подписи напиши:\n"
        "   • `real` - если это настоящее фото\n"
        "   • `ai` - если создано ИИ\n\n"
        "📝 Пример подписи: `real`\n\n"
        "После проверки фото появится в игре,\n"
        "а ты получишь достижение!",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    caption = message.caption or ""
    
    if caption.lower() not in ['real', 'ai']:
        bot.reply_to(
            message,
            "❌ Напиши в подписи `real` или `ai`!",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Скачиваем фото
    file_info = bot.get_file(message.photo[-1].file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    # Сохраняем
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"user_{message.from_user.id}_{timestamp}.jpg"
    file_path = os.path.join("images/suggested", filename)
    
    with open(file_path, 'wb') as f:
        f.write(downloaded_file)
    
    # Сохраняем в базу
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO suggestions (user_id, file_path, label, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (message.from_user.id, file_path, caption.lower(),
          datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()
    
    bot.reply_to(
        message,
        "✅ **Спасибо!**\n\n"
        "Фото отправлено на проверку.\n"
        "Когда его одобрят, ты получишь достижение!",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "🔙 НАЗАД")
def back(message):
    bot.reply_to(
        message,
        "👋 Главное меню:",
        reply_markup=get_main_keyboard()
    )

@bot.message_handler(func=lambda msg: msg.text == "❓ ПОМОЩЬ")
def help_message(message):
    bot.reply_to(
        message,
        "❓ **Как играть?**\n\n"
        "1️⃣ Жми 🎮 **ИГРАТЬ**\n"
        "2️⃣ Смотри на фото\n"
        "3️⃣ Выбирай:\n"
        "   📸 РЕАЛЬНОЕ или 🤖 ИИ\n\n"
        "🔍 **Как отличить ИИ?**\n"
        "• ИИ путает пальцы (6 вместо 5)\n"
        "• Текст часто бессмысленный\n"
        "• Тени падают странно\n"
        "• Глаза 'стеклянные'\n\n"
        "🏆 Играй, получай достижения\n"
        "и становись лучшим детективом!",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: True)
def all_other(message):
    bot.reply_to(
        message,
        "👇 **Просто выбери кнопку!**",
        reply_markup=get_main_keyboard()
    )

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("🚀 Запуск бота...")
    init_db()
    load_images()
    print("✅ Бот готов к работе!")
    
    # Бесконечный цикл с авто-перезапуском при ошибках
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print("🔄 Перезапуск через 5 секунд...")
            time.sleep(5)

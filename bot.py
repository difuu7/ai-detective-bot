# -*- coding: utf-8 -*-
import telebot
import os
import sqlite3
import csv
import json
import time
import random
from datetime import datetime, timedelta
from PIL import Image
import io
import threading
import schedule

# ========== НАСТРОЙКИ ==========
TOKEN = "8514983133:AAF4dvNmweMg8LOBVB2evu_bw3td3d_p8jM"
bot = telebot.TeleBot(TOKEN)

# Создаем папки
os.makedirs("images/real", exist_ok=True)
os.makedirs("images/ai", exist_ok=True)
os.makedirs("images/suggested", exist_ok=True)
os.makedirs("research_stats", exist_ok=True)

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
    
    # Таблица изображений с категориями
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT,
        label TEXT,
        filename TEXT,
        category TEXT DEFAULT 'other',
        subcategory TEXT DEFAULT '',
        difficulty INTEGER DEFAULT 1,
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
        
        for label in ['real', 'ai']:
            base_path = f"images/{label}"
            if os.path.exists(base_path):
                for category in os.listdir(base_path):
                    category_path = os.path.join(base_path, category)
                    if os.path.isdir(category_path):
                        for f in os.listdir(category_path):
                            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                                file_path = os.path.join(category_path, f)
                                cursor.execute('''
                                    INSERT INTO images (file_path, label, filename, category)
                                    VALUES (?, ?, ?, ?)
                                ''', (file_path, label, f, category))
        
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

# ========== ФУНКЦИЯ ИСПРАВЛЕНИЯ ФОТО ==========
def fix_image_size(file_path, max_size=1024):
    try:
        img = Image.open(file_path)
        width, height = img.size
        
        if width > max_size or height > max_size or width < 200 or height < 200:
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            
            if new_width < 300:
                new_width = 300
                new_height = int(height * (300 / width))
            
            img = img.resize((new_width, new_height), Image.LANCZOS)
            
            temp_path = file_path.replace('.', '_temp.')
            img.save(temp_path, quality=85, optimize=True)
            return temp_path
        
        return file_path
    except:
        return file_path

# ========== КЛАВИАТУРЫ ==========
def get_main_keyboard():
    keyboard = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        telebot.types.KeyboardButton("🎮 ИГРАТЬ"),
        telebot.types.KeyboardButton("📊 СТАТИСТИКА"),
        telebot.types.KeyboardButton("🏆 РЕЙТИНГ"),
        telebot.types.KeyboardButton("❓ ПОМОЩЬ")
    )
    return keyboard

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "👋 **Привет! Я ИИ-Детектив!**\n\n"
        "Я покажу тебе фото, а ты угадай: это реальное или создано ИИ?\n\n"
        "👇 **Выбирай кнопку ниже!**",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.reply_to(
        message,
        "❓ **Как играть?**\n\n"
        "1️⃣ Жми 🎮 ИГРАТЬ\n"
        "2️⃣ Смотри на фото\n"
        "3️⃣ Выбирай: РЕАЛЬНОЕ или ИИ\n\n"
        "🔍 **Советы:**\n"
        "• ИИ путает пальцы (6 вместо 5)\n"
        "• Текст часто бессмысленный\n"
        "• Тени падают странно",
        reply_markup=get_main_keyboard(),
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda msg: msg.text == "🎮 ИГРАТЬ")
@bot.message_handler(commands=['game'])
def game(message):
    image = get_random_image()
    
    if not image:
        bot.reply_to(message, "😕 Нет фото в базе")
        return
    
    image_id, file_path, correct_label = image
    
    current_games[message.chat.id] = {
        'image_id': image_id,
        'correct': correct_label,
        'start_time': time.time()
    }
    
    # Исправляем размер фото
    safe_path = fix_image_size(file_path)
    
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(
        telebot.types.InlineKeyboardButton("📸 РЕАЛЬНОЕ", callback_data=f"real_{image_id}"),
        telebot.types.InlineKeyboardButton("🤖 ИИ", callback_data=f"ai_{image_id}")
    )
    
    try:
        with open(safe_path, 'rb') as photo:
            bot.send_photo(
                message.chat.id,
                photo,
                caption="👇 **Как думаешь?**",
                reply_markup=keyboard
            )
        
        if safe_path != file_path:
            os.remove(safe_path)
            
    except Exception as e:
        bot.reply_to(message, f"😕 Ошибка: {e}")
        if safe_path != file_path and os.path.exists(safe_path):
            os.remove(safe_path)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('real_', 'ai_')))
def handle_answer(call):
    data = call.data.split('_')
    guess = data[0]
    image_id = int(data[1])
    user_id = call.from_user.id
    username = call.from_user.username or f"user_{user_id}"
    
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
    
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda msg: msg.text == "📊 СТАТИСТИКА")
@bot.message_handler(commands=['stats'])
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
    text += f"📈 Точность: {stats['accuracy']}%\n"
    text += f"🏆 Очки: {stats['score']}\n\n"
    text += f"🤖 Угадано ИИ: {stats['ai_correct']}\n"
    text += f"📸 Угадано фото: {stats['real_correct']}\n"
    text += f"🔥 Серия: {stats['streak']} (рекорд: {stats['max_streak']})"
    
    bot.reply_to(message, text, reply_markup=get_main_keyboard(), parse_mode="Markdown")

@bot.message_handler(func=lambda msg: msg.text == "🏆 РЕЙТИНГ")
@bot.message_handler(commands=['top'])
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

# ========== ИССЛЕДОВАТЕЛЬСКАЯ СТАТИСТИКА (ТОЛЬКО ДЛЯ ТЕБЯ) ==========
@bot.message_handler(commands=['research_stats'])
def research_stats(message):
    # 🔥 ЗАМЕНИ 123456789 НА СВОЙ TELEGRAM ID!
    MY_ID = 1960661466
    
    if message.from_user.id != MY_ID:
        bot.reply_to(message, "⛔ Нет доступа")
        return
    
    bot.send_message(message.chat.id, "📊 Начинаю сбор полной статистики...")
    
    try:
        conn = sqlite3.connect('ai_detective.db')
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        
        # ===== 1. СТАТИСТИКА ПО ПОЛЬЗОВАТЕЛЯМ =====
        cursor.execute("""
            SELECT user_id, username, score, games, correct, 
                   ROUND(100.0 * correct / games, 2) as accuracy,
                   streak, max_streak, ai_correct, real_correct
            FROM users WHERE games > 0 ORDER BY score DESC
        """)
        users_data = cursor.fetchall()
        
        with open(f"research_stats/users_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "username", "score", "games", "correct", "accuracy", 
                           "streak", "max_streak", "ai_correct", "real_correct"])
            writer.writerows(users_data)
        
        # ===== 2. СТАТИСТИКА ПО КАТЕГОРИЯМ =====
        cursor.execute("""
            SELECT 
                i.category,
                i.label,
                COUNT(*) as attempts,
                SUM(h.is_correct) as correct,
                ROUND(100.0 * SUM(h.is_correct) / COUNT(*), 2) as accuracy,
                ROUND(AVG(h.response_time), 2) as avg_time
            FROM history h
            JOIN images i ON h.image_id = i.id
            GROUP BY i.category, i.label
            ORDER BY i.category, accuracy
        """)
        category_data = cursor.fetchall()
        
        with open(f"research_stats/categories_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["category", "type", "attempts", "correct", "accuracy", "avg_time"])
            writer.writerows(category_data)
        
        # ===== 3. СВОДНАЯ ПО КАТЕГОРИЯМ =====
        cursor.execute("""
            SELECT 
                i.category,
                COUNT(*) as attempts,
                SUM(h.is_correct) as correct,
                ROUND(100.0 * SUM(h.is_correct) / COUNT(*), 2) as accuracy
            FROM history h
            JOIN images i ON h.image_id = i.id
            GROUP BY i.category
            ORDER BY accuracy
        """)
        category_summary = cursor.fetchall()
        
        # ===== 4. ДИНАМИКА ПО ДНЯМ =====
        cursor.execute("""
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as games,
                SUM(is_correct) as correct,
                ROUND(100.0 * SUM(is_correct) / COUNT(*), 2) as accuracy
            FROM history
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 30
        """)
        daily_data = cursor.fetchall()
        
        with open(f"research_stats/daily_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["date", "games", "correct", "accuracy"])
            writer.writerows(daily_data)
        
        # ===== 5. СРАВНЕНИЕ ИИ VS РЕАЛЬНЫЕ =====
        cursor.execute("""
            SELECT 
                i.label,
                COUNT(*) as total,
                SUM(h.is_correct) as correct,
                ROUND(100.0 * SUM(h.is_correct) / COUNT(*), 2) as accuracy
            FROM history h
            JOIN images i ON h.image_id = i.id
            GROUP BY i.label
        """)
        comparison_data = cursor.fetchall()
        
        with open(f"research_stats/comparison_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["type", "total", "correct", "accuracy"])
            writer.writerows(comparison_data)
        
        # ===== 6. САМЫЕ СЛОЖНЫЕ ИЗОБРАЖЕНИЯ =====
        cursor.execute("""
            SELECT 
                i.filename,
                i.category,
                i.label,
                i.times_used,
                i.times_used - i.correct_count as wrong,
                ROUND(100.0 * (i.times_used - i.correct_count) / i.times_used, 2) as error_rate
            FROM images i
            WHERE i.times_used >= 5
            ORDER BY error_rate DESC
            LIMIT 20
        """)
        hardest_data = cursor.fetchall()
        
        with open(f"research_stats/hardest_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["filename", "category", "type", "attempts", "wrong", "error_rate"])
            writer.writerows(hardest_data)
        
        # ===== 7. САМЫЕ ЛЕГКИЕ ИЗОБРАЖЕНИЯ =====
        cursor.execute("""
            SELECT 
                i.filename,
                i.category,
                i.label,
                i.times_used,
                i.correct_count,
                ROUND(100.0 * i.correct_count / i.times_used, 2) as accuracy
            FROM images i
            WHERE i.times_used >= 5
            ORDER BY accuracy DESC
            LIMIT 20
        """)
        easiest_data = cursor.fetchall()
        
        with open(f"research_stats/easiest_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["filename", "category", "type", "attempts", "correct", "accuracy"])
            writer.writerows(easiest_data)
        
        # ===== 8. ОБЩАЯ СТАТИСТИКА =====
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE games > 0")
        active_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM history")
        total_games = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(is_correct) FROM history")
        total_correct = cursor.fetchone()[0] or 0
        
        conn.close()
        
        avg_accuracy = round((total_correct / total_games) * 100, 2) if total_games > 0 else 0
        
        # Сохраняем общую статистику
        with open(f"research_stats/summary_{timestamp}.txt", 'w', encoding='utf-8') as f:
            f.write(f"Дата сбора: {datetime.now()}\n")
            f.write(f"Всего пользователей: {total_users}\n")
            f.write(f"Активных: {active_users}\n")
            f.write(f"Всего игр: {total_games}\n")
            f.write(f"Правильных ответов: {total_correct}\n")
            f.write(f"Средняя точность: {avg_accuracy}%\n")
        
        # Сохраняем JSON
        full_stats = {
            "date": str(datetime.now()),
            "total_users": total_users,
            "active_users": active_users,
            "total_games": total_games,
            "total_correct": total_correct,
            "avg_accuracy": avg_accuracy
        }
        
        with open(f"research_stats/full_stats_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(full_stats, f, indent=2)
        
        # Отправляем результат
        result_text = (
            f"✅ ПОЛНАЯ СТАТИСТИКА СОБРАНА!\n\n"
            f"📁 Создано файлов:\n"
            f"• users_{timestamp}.csv\n"
            f"• categories_{timestamp}.csv\n"
            f"• daily_{timestamp}.csv\n"
            f"• hardest_{timestamp}.csv\n"
            f"• easiest_{timestamp}.csv\n"
            f"• comparison_{timestamp}.csv\n"
            f"• summary_{timestamp}.txt\n"
            f"• full_stats_{timestamp}.json\n\n"
            f"📊 Всего игр: {total_games}\n"
            f"📈 Точность: {avg_accuracy}%\n\n"
            f"Используй /list_stats и /get_stats"
        )
        
        bot.send_message(message.chat.id, result_text)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.message_handler(commands=['list_stats'])
def list_stats(message):
    MY_ID = 1960661466  # 🔥 ТВОЙ ID
    if message.from_user.id != MY_ID:
        bot.reply_to(message, "⛔ Нет доступа")
        return
    
    files = os.listdir("research_stats")
    if not files:
        bot.reply_to(message, "📭 Папка статистики пуста")
        return
    
    files.sort(reverse=True)
    text = "📁 **Файлы статистики:**\n\n"
    for f in files[:15]:
        size = os.path.getsize(f"research_stats/{f}")
        if size < 1024:
            size_str = f"{size} B"
        elif size < 1024*1024:
            size_str = f"{size/1024:.1f} KB"
        else:
            size_str = f"{size/1024/1024:.1f} MB"
        text += f"• {f} ({size_str})\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['get_stats'])
def get_stats(message):
    MY_ID = 1960661466  # 🔥 ТВОЙ ID
    if message.from_user.id != MY_ID:
        bot.reply_to(message, "⛔ Нет доступа")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        files = sorted(os.listdir("research_stats"), reverse=True)[:5]
        file_list = "\n".join([f"• {f}" for f in files])
        bot.reply_to(message, 
            f"❌ Укажи имя файла: `/get_stats имя_файла`\n\n"
            f"Последние файлы:\n{file_list}",
            parse_mode="Markdown"
        )
        return
    
    filename = parts[1]
    filepath = os.path.join("research_stats", filename)
    
    if not os.path.exists(filepath):
        bot.reply_to(message, f"❌ Файл {filename} не найден")
        return
    
    with open(filepath, 'rb') as f:
        bot.send_document(message.chat.id, f, caption=f"📊 {filename}")

# ===== ОБРАБОТЧИК НЕИЗВЕСТНЫХ КОМАНД =====
@bot.message_handler(func=lambda message: message.text and message.text.startswith('/'))
def unknown_command(message):
    bot.reply_to(
        message,
        "❓ Неизвестная команда. Используй /help",
        reply_markup=get_main_keyboard()
    )

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    print("="*60)
    print("🚀 ЗАПУСК БОТА С ИССЛЕДОВАТЕЛЬСКОЙ СТАТИСТИКОЙ")
    print("="*60)
    
    init_db()
    load_images()
    
    print("\n✅ ИССЛЕДОВАТЕЛЬСКИЕ КОМАНДЫ:")
    print("   • /research_stats - собрать полную статистику")
    print("   • /list_stats - список файлов")
    print("   • /get_stats - скачать файл")
    print("="*60)
    
    bot.infinity_polling()

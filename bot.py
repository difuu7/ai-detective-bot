# -*- coding: utf-8 -*-
import telebot
import os
import random
import sqlite3
import time
from datetime import datetime, timedelta
import threading
import schedule
import os
import json
import csv
from datetime import datetime
from PIL import Image
import io

# Папка для исследовательской статистики
STATS_DIR = "research_stats"
os.makedirs(STATS_DIR, exist_ok=True)

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
    
    # Таблица пользователей (оставляем как есть)
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
    
    # Таблица изображений с категориями (НОВАЯ)
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
    print("✅ База данных обновлена")

def load_images():
    """Загружает изображения из папок с категориями"""
    conn = sqlite3.connect('ai_detective.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM images")
    if cursor.fetchone()[0] == 0:
        print("📸 Загружаем изображения с категориями...")
        
        # Проходим по всем папкам
        for label in ['real', 'ai']:
            base_path = f"images/{label}"
            if os.path.exists(base_path):
                # Проходим по всем подпапкам (категориям)
                for category in os.listdir(base_path):
                    category_path = os.path.join(base_path, category)
                    if os.path.isdir(category_path):
                        # Проходим по файлам в папке категории
                        for f in os.listdir(category_path):
                            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                                file_path = os.path.join(category_path, f)
                                cursor.execute("""
                                    INSERT INTO images 
                                    (file_path, label, filename, category) 
                                    VALUES (?, ?, ?, ?)
                                """, (file_path, label, f, category))
                                print(f"  + {label}/{category}: {f}")
        
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM images")
        total = cursor.fetchone()[0]
        
        # Показываем статистику по категориям
        cursor.execute("SELECT category, label, COUNT(*) FROM images GROUP BY category, label")
        stats = cursor.fetchall()
        print(f"\n✅ Загружено {total} изображений:")
        for cat, lbl, cnt in stats:
            emoji = "📸" if lbl == 'real' else "🤖"
            print(f"  {emoji} {cat}: {cnt}")
    
    conn.close()

def save_stats_to_json(data, filename):
    """Сохраняет данные в JSON файл"""
    filepath = os.path.join(STATS_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ JSON сохранен: {filename}")

def save_stats_to_csv(data, filename, headers):
    """Сохраняет данные в CSV файл (для Excel)"""
    filepath = os.path.join(STATS_DIR, filename)
    with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    print(f"✅ CSV сохранен: {filename}")

def guess_category_from_filename(filename):
    """Определяет категорию изображения по имени файла"""
    filename = filename.lower()
    
    categories = {
        'people': ['person', 'people', 'man', 'woman', 'child', 'girl', 'boy', 'portrait', 'face', 'human'],
        'animals': ['cat', 'dog', 'animal', 'pet', 'bird', 'fish', 'horse', 'cow', 'pig', 'lion', 'tiger', 'bear'],
        'nature': ['nature', 'landscape', 'mountain', 'forest', 'tree', 'flower', 'plant', 'sky', 'cloud', 'sunset', 'sunrise', 'beach', 'ocean', 'sea', 'river', 'lake'],
        'urban': ['city', 'urban', 'building', 'street', 'road', 'house', 'architecture', 'town', 'village'],
        'food': ['food', 'pizza', 'burger', 'cake', 'pasta', 'rice', 'soup', 'salad', 'fruit', 'vegetable', 'meal', 'drink', 'coffee', 'tea'],
        'objects': ['object', 'item', 'thing', 'product', 'gadget', 'device', 'tool', 'furniture', 'chair', 'table', 'bed', 'car', 'vehicle'],
        'art': ['art', 'painting', 'drawing', 'sketch', 'digital', 'abstract', 'cartoon', 'anime'],
        'other': []
    }
    
    for category, keywords in categories.items():
        for keyword in keywords:
            if keyword in filename:
                return category
    
    return 'other'

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

@bot.message_handler(commands=['🎮 ИГРАТЬ'])
def play(message):
    image = get_random_image()
    
    if not image:
        bot.reply_to(message, "😕 Нет фото в базе")
        return
    
    image_id, file_path, correct_label = image
    
    # 🔧 АВТОМАТИЧЕСКИ ИСПРАВЛЯЕМ РАЗМЕР ФОТО
    safe_path = fix_image_size(file_path)
    
    # Создаем клавиатуру
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.row(
        telebot.types.InlineKeyboardButton("📸 РЕАЛЬНОЕ", callback_data=f"real_{image_id}"),
        telebot.types.InlineKeyboardButton("🤖 ИИ", callback_data=f"ai_{image_id}")
    )
    
    try:
        # Отправляем фото (исправленное или оригинал)
        with open(safe_path, 'rb') as photo:
            bot.send_photo(
                message.chat.id,
                photo,
                caption="👇 **Как думаешь?**",
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
        # Если использовали временный файл - удаляем его
        if safe_path != file_path:
            os.remove(safe_path)
            print(f"🗑️ Временный файл удален: {os.path.basename(safe_path)}")
            
    except Exception as e:
        bot.reply_to(message, f"😕 Ошибка загрузки фото: {e}")
        # Если ошибка, тоже удаляем временный файл
        if safe_path != file_path and os.path.exists(safe_path):
            os.remove(safe_path)

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

# ========== ПОЛНАЯ ИССЛЕДОВАТЕЛЬСКАЯ СТАТИСТИКА ==========
@bot.message_handler(commands=['research_stats'])
def research_stats(message):
    # 🔥 ЗАМЕНИ 123456789 НА СВОЙ TELEGRAM ID!
    MY_ID = 1960661466
    
    # Проверяем, что команду вызвал ты
    if message.from_user.id != MY_ID:
        bot.reply_to(message, "⛔ Эта команда только для исследователя")
        return
    
    bot.send_message(message.chat.id, "📊 **Начинаю сбор полной статистики...**", parse_mode="Markdown")
    
    try:
        conn = sqlite3.connect('ai_detective.db')
        cursor = conn.cursor()
        
        # Создаем папку для статистики
        os.makedirs("research_stats", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        
        # ===== 1. СТАТИСТИКА ПО ПОЛЬЗОВАТЕЛЯМ =====
        cursor.execute("""
            SELECT 
                user_id,
                username,
                score,
                games,
                correct,
                ROUND(100.0 * correct / games, 2) as accuracy,
                streak,
                max_streak,
                ai_correct,
                real_correct,
                contributed
            FROM users
            WHERE games > 0
            ORDER BY score DESC
        """)
        users_data = cursor.fetchall()
        
        with open(f"research_stats/users_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "username", "score", "games", "correct", "accuracy", 
                           "streak", "max_streak", "ai_correct", "real_correct", "contributed"])
            writer.writerows(users_data)
        
        # ===== 2. СТАТИСТИКА ПО КАТЕГОРИЯМ (ПОЛНАЯ) =====
        cursor.execute("""
            SELECT 
                i.category,
                i.label,
                COUNT(*) as attempts,
                SUM(h.is_correct) as correct,
                ROUND(100.0 * SUM(h.is_correct) / COUNT(*), 2) as accuracy,
                ROUND(AVG(h.response_time), 2) as avg_time,
                MIN(h.response_time) as min_time,
                MAX(h.response_time) as max_time
            FROM history h
            JOIN images i ON h.image_id = i.id
            GROUP BY i.category, i.label
            ORDER BY i.category, accuracy
        """)
        category_data = cursor.fetchall()
        
        with open(f"research_stats/categories_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["category", "type", "attempts", "correct", "accuracy", 
                           "avg_time", "min_time", "max_time"])
            writer.writerows(category_data)
        
        # ===== 3. СВОДНАЯ ПО КАТЕГОРИЯМ =====
        cursor.execute("""
            SELECT 
                i.category,
                COUNT(*) as total_attempts,
                SUM(h.is_correct) as total_correct,
                ROUND(100.0 * SUM(h.is_correct) / COUNT(*), 2) as accuracy,
                ROUND(AVG(h.response_time), 2) as avg_time
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
                ROUND(100.0 * SUM(is_correct) / COUNT(*), 2) as accuracy,
                ROUND(AVG(response_time), 2) as avg_time
            FROM history
            GROUP BY DATE(timestamp)
            ORDER BY date DESC
            LIMIT 30
        """)
        daily_data = cursor.fetchall()
        
        with open(f"research_stats/daily_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["date", "games", "correct", "accuracy", "avg_time"])
            writer.writerows(daily_data)
        
        # ===== 5. СРАВНЕНИЕ ИИ VS РЕАЛЬНЫЕ =====
        cursor.execute("""
            SELECT 
                i.label,
                COUNT(*) as total,
                SUM(h.is_correct) as correct,
                ROUND(100.0 * SUM(h.is_correct) / COUNT(*), 2) as accuracy,
                ROUND(AVG(h.response_time), 2) as avg_time
            FROM history h
            JOIN images i ON h.image_id = i.id
            GROUP BY i.label
        """)
        comparison_data = cursor.fetchall()
        
        with open(f"research_stats/comparison_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["type", "total", "correct", "accuracy", "avg_time"])
            writer.writerows(comparison_data)
        
        # ===== 6. САМЫЕ СЛОЖНЫЕ ИЗОБРАЖЕНИЯ (ТОП-20) =====
        cursor.execute("""
            SELECT 
                i.filename,
                i.category,
                i.label,
                i.times_used,
                i.correct_count,
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
            writer.writerow(["filename", "category", "type", "attempts", "correct", "wrong", "error_rate"])
            writer.writerows(hardest_data)
        
        # ===== 7. САМЫЕ ЛЕГКИЕ ИЗОБРАЖЕНИЯ (ТОП-20) =====
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
        
        # ===== 8. СТАТИСТИКА ПО ВРЕМЕНИ ОТВЕТА =====
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN response_time < 3 THEN 'быстро (<3 сек)'
                    WHEN response_time BETWEEN 3 AND 7 THEN 'средне (3-7 сек)'
                    ELSE 'медленно (>7 сек)'
                END as speed,
                COUNT(*) as count,
                SUM(is_correct) as correct,
                ROUND(100.0 * SUM(is_correct) / COUNT(*), 2) as accuracy
            FROM history
            GROUP BY speed
        """)
        speed_data = cursor.fetchall()
        
        with open(f"research_stats/speed_{timestamp}.csv", 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow(["speed", "count", "correct", "accuracy"])
            writer.writerows(speed_data)
        
        # ===== 9. ОБЩАЯ СТАТИСТИКА =====
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM users WHERE games > 0")
        active_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM history")
        total_games = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(is_correct) FROM history")
        total_correct = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT AVG(response_time) FROM history")
        avg_response = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT COUNT(*) FROM images WHERE label='real'")
        real_images = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM images WHERE label='ai'")
        ai_images = cursor.fetchone()[0]
        
        conn.close()
        
        avg_accuracy = round((total_correct / total_games) * 100, 2) if total_games > 0 else 0
        
        # Сохраняем общую статистику
        with open(f"research_stats/summary_{timestamp}.txt", 'w', encoding='utf-8') as f:
            f.write("========== ОБЩАЯ СТАТИСТИКА ==========\n")
            f.write(f"Дата сбора: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Пользователи:\n")
            f.write(f"  Всего: {total_users}\n")
            f.write(f"  Активных: {active_users}\n")
            f.write(f"  Неактивных: {total_users - active_users}\n\n")
            f.write(f"Игры:\n")
            f.write(f"  Всего игр: {total_games}\n")
            f.write(f"  Правильных ответов: {total_correct}\n")
            f.write(f"  Ошибок: {total_games - total_correct}\n")
            f.write(f"  Средняя точность: {avg_accuracy}%\n")
            f.write(f"  Среднее время ответа: {round(avg_response, 2)} сек\n\n")
            f.write(f"Изображения:\n")
            f.write(f"  Реальных фото: {real_images}\n")
            f.write(f"  ИИ-картинок: {ai_images}\n")
            f.write(f"  Всего: {real_images + ai_images}\n\n")
            
            f.write("========== СТАТИСТИКА ПО КАТЕГОРИЯМ ==========\n")
            for cat, total, correct, acc, avg_t in category_summary:
                f.write(f"{cat}:\n")
                f.write(f"  Игр: {total}\n")
                f.write(f"  Точность: {acc}%\n")
                f.write(f"  Среднее время: {avg_t} сек\n\n")
            
            if comparison_data:
                f.write("========== СРАВНЕНИЕ ИИ VS РЕАЛЬНЫЕ ==========\n")
                for label, total, correct, acc, avg_t in comparison_data:
                    emoji = "🤖" if label == 'ai' else "📸"
                    f.write(f"{emoji} {label.upper()}:\n")
                    f.write(f"  Игр: {total}\n")
                    f.write(f"  Точность: {acc}%\n")
                    f.write(f"  Среднее время: {avg_t} сек\n\n")
        
        # Создаем JSON со всеми данными
        full_stats = {
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_users": total_users,
            "active_users": active_users,
            "total_games": total_games,
            "total_correct": total_correct,
            "avg_accuracy": avg_accuracy,
            "avg_response_time": round(avg_response, 2),
            "images": {
                "real": real_images,
                "ai": ai_images
            },
            "categories": {},
            "comparison": {},
            "hardest": [],
            "easiest": []
        }
        
        for cat, total, correct, acc, avg_t in category_summary:
            full_stats["categories"][cat] = {
                "attempts": total,
                "accuracy": acc,
                "avg_time": avg_t
            }
        
        for label, total, correct, acc, avg_t in comparison_data:
            full_stats["comparison"][label] = {
                "attempts": total,
                "accuracy": acc,
                "avg_time": avg_t
            }
        
        for img, cat, label, attempts, correct, wrong, error in hardest_data:
            full_stats["hardest"].append({
                "filename": img,
                "category": cat,
                "type": label,
                "attempts": attempts,
                "error_rate": error
            })
        
        for img, cat, label, attempts, correct, acc in easiest_data:
            full_stats["easiest"].append({
                "filename": img,
                "category": cat,
                "type": label,
                "attempts": attempts,
                "accuracy": acc
            })
        
        with open(f"research_stats/full_stats_{timestamp}.json", 'w', encoding='utf-8') as f:
            json.dump(full_stats, f, ensure_ascii=False, indent=2)
        
        # Формируем краткий отчет для Telegram
        report = f"✅ **ПОЛНАЯ СТАТИСТИКА СОБРАНА!**\n\n"
        report += f"📁 **Создано файлов:**\n"
        report += f"• users_{timestamp}.csv - данные игроков\n"
        report += f"• categories_{timestamp}.csv - детально по категориям\n"
        report += f"• daily_{timestamp}.csv - активность по дням\n"
        report += f"• hardest_{timestamp}.csv - топ-20 сложных фото\n"
        report += f"• easiest_{timestamp}.csv - топ-20 легких фото\n"
        report += f"• speed_{timestamp}.csv - анализ скорости ответов\n"
        report += f"• full_stats_{timestamp}.json - все данные в JSON\n\n"
        
        report += f"📊 **Ключевые показатели:**\n"
        report += f"• 👥 Всего пользователей: {total_users}\n"
        report += f"• 🎮 Сыграно игр: {total_games}\n"
        report += f"• 📈 Общая точность: {avg_accuracy}%\n"
        report += f"• ⏱ Среднее время: {round(avg_response, 2)} сек\n\n"
        
        # Добавляем сравнение категорий
        if category_summary:
            best_cat = max(category_summary, key=lambda x: x[3])
            worst_cat = min(category_summary, key=lambda x: x[3])
            report += f"🏆 **Лучшая категория:** {best_cat[0]} ({best_cat[3]}%)\n"
            report += f"📉 **Худшая категория:** {worst_cat[0]} ({worst_cat[3]}%)\n\n"
        
        # Добавляем сравнение ИИ vs Реальные
        if len(comparison_data) == 2:
            ai_acc = comparison_data[0][3] if comparison_data[0][0] == 'ai' else comparison_data[1][3]
            real_acc = comparison_data[1][3] if comparison_data[1][0] == 'real' else comparison_data[0][3]
            diff = abs(ai_acc - real_acc)
            report += f"🤖 **ИИ распознают:** {ai_acc}%\n"
            report += f"📸 **Реальные фото:** {real_acc}%\n"
            report += f"📊 **Разница:** {diff}%\n\n"
        
        report += f"📥 **Скачай файлы командой:** `/get_stats имя_файла`"
        
        bot.send_message(message.chat.id, report,)
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка при сборе статистики: {e}")
        import traceback
        traceback.print_exc()

@bot.message_handler(commands=['list_stats'])
def list_stats(message):
    MY_ID = 1960661466  # 🔥 ТВОЙ ID
    if message.from_user.id != MY_ID:
        bot.reply_to(message, "⛔ Нет доступа")
        return
    
    try:
        files = os.listdir("research_stats")
        if not files:
            bot.reply_to(message, "📭 Папка статистики пуста. Сначала выполни /research_stats")
            return
        
        # Сортируем от новых к старым
        files.sort(reverse=True)
        
        text = "📁 **Файлы статистики:**\n\n"
        for f in files[:10]:  # показываем последние 10
            size = os.path.getsize(os.path.join("research_stats", f))
            if size < 1024:
                size_str = f"{size} B"
            elif size < 1024*1024:
                size_str = f"{size/1024:.1f} KB"
            else:
                size_str = f"{size/1024/1024:.1f} MB"
            
            text += f"• {f} ({size_str})\n"
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

# ========== ПОЛУЧЕНИЕ ФАЙЛОВ СТАТИСТИКИ ==========
@bot.message_handler(commands=['get_stats'])
def get_stats(message):
    # 🔥 ТВОЙ TELEGRAM ID
    MY_ID = 1960661466
    
    # Проверка доступа (только для тебя)
    if message.from_user.id != MY_ID:
        bot.reply_to(message, "⛔ Нет доступа к этой команде")
        return
    
    # Разбираем команду: /get_stats filename.csv
    parts = message.text.split()
    
    # Если пользователь не указал имя файла
    if len(parts) < 2:
        # Показываем список последних файлов
        try:
            files = os.listdir("research_stats")
            files.sort(reverse=True)  # новые сверху
            recent_files = files[:5]  # последние 5
            
            if not recent_files:
                bot.reply_to(message, "📭 Папка статистики пуста. Сначала выполни /research_stats")
                return
            
            file_list = "\n".join([f"• {f}" for f in recent_files])
            bot.reply_to(message, 
                f"❌ Укажи имя файла: `/get_stats имя_файла`\n\n"
                f"Последние файлы:\n{file_list}",
                parse_mode="Markdown"
            )
        except Exception as e:
            bot.reply_to(message, f"❌ Ошибка при чтении папки: {e}")
        return
    
    # Получаем имя файла из команды
    filename = parts[1]
    filepath = os.path.join("research_stats", filename)
    
    # Проверяем, существует ли файл
    if not os.path.exists(filepath):
        bot.reply_to(message, f"❌ Файл '{filename}' не найден в папке research_stats")
        return
    
    # Отправляем файл пользователю
    try:
        with open(filepath, 'rb') as f:
            bot.send_document(
                chat_id=message.chat.id,
                document=f,
                caption=f"📊 Файл статистики: {filename}"
            )
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка при отправке файла: {e}")

def fix_image_size(file_path, max_size=1024):
    """
    Проверяет и исправляет размер изображения для Telegram
    Возвращает путь к исправленному файлу
    """
    try:
        # Открываем изображение
        img = Image.open(file_path)
        width, height = img.size
        
        print(f"📸 Проверяю: {os.path.basename(file_path)} [{width}x{height}]")
        
        # Проверяем, нужно ли менять размер
        needs_resize = False
        new_width, new_height = width, height
        
        if width > max_size or height > max_size:
            # Уменьшаем, сохраняя пропорции
            if width > height:
                new_width = max_size
                new_height = int(height * (max_size / width))
            else:
                new_height = max_size
                new_width = int(width * (max_size / height))
            needs_resize = True
            print(f"   📏 Слишком большое: {width}x{height} -> {new_width}x{new_height}")
        
        elif width < 200 or height < 200:
            # Увеличиваем маленькие фото
            if width < height:
                new_width = 300
                new_height = int(height * (300 / width))
            else:
                new_height = 300
                new_width = int(width * (300 / height))
            needs_resize = True
            print(f"   📏 Слишком маленькое: {width}x{height} -> {new_width}x{new_height}")
        
        if needs_resize:
            # Изменяем размер
            img = img.resize((new_width, new_height), Image.LANCZOS)
            
            # Создаем временный файл
            temp_path = file_path.replace('.', '_temp.')
            img.save(temp_path, quality=85, optimize=True)
            print(f"   ✅ Исправлено: {os.path.basename(temp_path)}")
            return temp_path
        
        print(f"   ✅ Размер нормальный")
        return file_path
        
    except Exception as e:
        print(f"❌ Ошибка при обработке {file_path}: {e}")
        return file_path

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

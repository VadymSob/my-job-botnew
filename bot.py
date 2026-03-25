import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import json

# --- НАЛАШТУВАННЯ ВАШОГО "ШІ-РЕКРУТЕРА" ---
AI_CRITERIA = """
Шукаємо Комерційного директора у Вінниці.
Критерії відбору:
1. Обов'язковий досвід на керівних посадах (директор, нач. відділу).
2. Бажано досвід у продажах або комерції.
3. НЕ підходять кандидати без досвіду або суто технічні спеціалісти.
Відсіюй тих, хто явно не відповідає рівню топ-менеджменту.
"""

def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "⚠️ Помилка: Немає API ключа Gemini"

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = f"""
    Ти - професійний рекрутер. Проаналізуй список кандидатів нижче згідно з цими критеріями:
    {AI_CRITERIA}

    Список кандидатів:
    {candidate_data}

    Для кожного підходящого кандидата напиши:
    ✅ [Ім'я/Посада] - [Чому підходить коротко] - [Посилання]
    
    Якщо кандидат не підходить, просто проігноруй його.
    В кінці додай коротке резюме: "Знайдено X цікавих кандидатів".
    """

    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=30)
        result = r.json()
        return result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"❌ Помилка ШІ-аналізу: {e}"

def get_work_ua():
    base_url = "https://www.work.ua/resumes-vinnytsya-"
    query = urllib.parse.quote("комерційний директор")
    url = f"{base_url}{query}/"
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        
        candidates_raw = ""
        for card in cards[:10]: # Даємо ШІ на аналіз 10 кандидатів
            link_tag = card.find('a', href=True)
            info_tag = card.find('p', class_='text-muted')
            if link_tag:
                name = link_tag.get_text(strip=True)
                info = info_tag.get_text(strip=True) if info_tag else ""
                link = "https://www.work.ua" + link_tag['href']
                candidates_raw += f"Кандидат: {name}. Опис: {info}. Посилання: {link}\n\n"
        
        return candidates_raw
    except: return ""

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

if __name__ == "__main__":
    raw_data = get_work_ua()
    if raw_data:
        ai_report = get_ai_analysis(raw_data)
        send_telegram(f"🤖 **ШІ-аналіз нових резюме**\n\n{ai_report}")
    else:
        send_telegram("📭 Нових кандидатів для аналізу не знайдено.")

import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

# --- 1. ВАШІ КРИТЕРІЇ ДЛЯ ШІ ---
AI_CRITERIA = """
Ти - професійний рекрутер, що працює на хлібозавод у Вінницькій області. 
Шукаємо: Керівника відділу продажу або Комерційного директора.
Специфіка: Хлібобулочні вироби (швидкопсувний товар, FMCG).
СИТУАЦІЯ: Продажі падають, висока конкуренція. Потрібен лідер, який врятує продажі.

КРИТЕРІЇ ВІДБОРУ:
1. ДОСВІД: Тільки FMCG (продукти харчування). Досвід з хлібом, молочкою, м'ясом - пріоритет.
2. СКІЛИ: Управління командою, навчання менеджерів, розвиток території Вінниччини.
3. ЕКОНОМІКА: Розуміння маржі, повернень, виконання планів реалізації.

ТВОЄ ЗАВДАННЯ:
- Проаналізуй список кандидатів.
- Відсій тих, хто не з продуктів або не має досвіду управління людьми.
- Для кожного підходящого напиши: ✅ [ПІБ/Посада] - чому підходить - [Посилання].
- В кінці додай короткий висновок.
"""

# --- 2. ФУНКЦІЯ АНАЛІЗУ ЧЕРЕЗ GEMINI ---
def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: 
        return "⚠️ Помилка: GEMINI_API_KEY не знайдено в Secrets GitHub."

    # Використовуємо стабільну версію v1 та модель gemini-1.5-flash
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    prompt = f"{AI_CRITERIA}\n\nСписок кандидатів для аналізу:\n{candidate_data}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "safetySettings": [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
        ]
    }
    
    try:
        r = requests.post(url, json=payload, timeout=30)
        res = r.json()
        
        # Обробка відповіді
        if 'candidates' in res and len(res['candidates']) > 0:
            content = res['candidates'][0].get('content')
            if content and 'parts' in content:
                return content['parts'][0]['text']
            else:
                return "⚠️ ШІ повернув порожню відповідь (кандидати відфільтровані або помилка вмісту)."
        elif 'error' in res:
            return f"❌ Помилка Google API: {res['error'].get('message', 'Unknown error')}"
        else:
            return f"⚠️ Неочікувана відповідь від ШІ. Перевірте структуру: {str(res)[:200]}"
    except Exception as e:
        return f"❌ Технічна помилка зв'язку з ШІ: {str(e)}"

# --- 3. ЗБІР ДАНИХ З WORK.UA ---
def get_work_ua_data():
    query = urllib.parse.quote("комерційний директор")
    url = f"https://www.work.ua/resumes-vinnytsya-{query}/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Cookie": os.getenv("WORK_UA_COOKIE", "")
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        
        if not cards:
            return None

        candidates_text = ""
        for card in cards[:12]: 
            link_tag = card.find('a', href=True)
            info_tag = card.find('p', class_='text-muted')
            if link_tag:
                name = link_tag.get_text(strip=True)
                info = info_tag.get_text(strip=True) if info_tag else "Досвід не вказано"
                link = "https://www.work.ua" + link_tag['href']
                candidates_text += f"КАНДИДАТ: {name}\nІНФО: {info}\nПОСИЛАННЯ: {link}\n\n"
        
        return candidates_text
    except Exception as e:
        return None

# --- 4. НАДІСЛАННЯ В TELEGRAM ---
def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id: return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    if len(message) > 4000:
        message = message[:4000] + "..."
        
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, data=payload)

# --- 5. ГОЛОВНИЙ ЗАПУСК ---
if __name__ == "__main__":
    raw_data = get_work_ua_data()
    
    if raw_data:
        final_report = get_ai_analysis(raw_data)
        send_telegram(f"🤖 **Звіт ШІ-рекрутера (Хлібозавод):**\n\n{final_report}")
    else:
        send_telegram("📭 Сьогодні на Work.ua нових кандидатів не знайдено.")

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

    # Використовуємо повний шлях до моделі, який зазвичай виправляє помилку "not found"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={api_key}"
    
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
        
        # Перевірка наявності відповіді
        if 'candidates' in res and len(res['candidates']) > 0:
            content = res['candidates'][0].get('content')
            if content and 'parts' in content:
                return content['parts'][0]['text']
            else:
                return "⚠️ ШІ не зміг сформувати текст (можливо, через внутрішні фільтри)."
        elif 'error' in res:
            # Якщо gemini-pro теж не знайдено, спробуємо gemini-1.5-pro як останній шанс
            return f"❌ Помилка API: {res['error'].get('message')}"
        else:
            return "⚠️ Невідома помилка відповіді ШІ."
    except Exception as e:
        return f"❌ Технічна помилка зв'язку: {str(e)}"

# --- 3. ЗБІР ДАНИХ З WORK.UA ---
def get_work_ua_data():
    query = urllib.parse.quote("комерційний директор")
    url = f"https://www.work.ua/resumes-vinnytsya-{query}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": os.getenv("WORK_UA_COOKIE", "")
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        if not cards: return None
        data = ""
        for card in cards[:12]: 
            link = card.find('a', href=True)
            info = card.find('p', class_='text-muted')
            if link:
                data += f"КАНДИДАТ: {link.get_text(strip=True)}\nІНФО: {info.get_text(strip=True) if info else ''}\nПОСИЛАННЯ: https://www.work.ua{link['href']}\n\n"
        return data
    except: return None

# --- 4. НАДІСЛАННЯ В TELEGRAM ---
def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    if len(message) > 4000: message = message[:4000] + "..."
    requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True})

if __name__ == "__main__":
    raw_candidates = get_work_ua_data()
    if raw_candidates:
        final_report = get_ai_analysis(raw_candidates)
        send_telegram(f"🤖 **Звіт ШІ-рекрутера (Хлібозавод):**\n\n{final_report}")
    else:
        send_telegram("📭 Сьогодні нових резюме на Work.ua не знайдено.")

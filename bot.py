import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

# --- КРИТЕРІЇ ШІ-РЕКРУТЕРА ---
AI_CRITERIA = """
Ти - комерційний директор хлібозаводу. Шукаємо Керівника відділу продажу або Комерційного директора (Вінницька обл.).
Специфіка: Хлібобулочні вироби (швидкопсувний товар).
СИТУАЦІЯ: Продажі падають, конкуренція зростає. 

КРИТЕРІЇ ВІДБОРУ:
1. ДОСВІД: Обов'язково FMCG (продукти харчування). Хліб, молочка, м'ясо - пріоритет.
2. СКІЛИ: Побудова системних продажів, навчання менеджерів, розвиток території Вінниччини.
3. ЕКОНОМІКА: Розуміння маржі, повернень, цілей по об'ємах.

ЗАВДАННЯ: 
- Проаналізуй список кандидатів.
- Відсій тих, хто не з продуктів або не має досвіду управління.
- Напиши результат для кожного підходящого: "✅ ПІБ - чому підходить - посилання".
"""

def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "⚠️ Помилка: Не додано GEMINI_API_KEY у Secrets."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = f"{AI_CRITERIA}\n\nСписок кандидатів:\n{candidate_data}"
    
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=30)
        res = r.json()
        return res['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"❌ Помилка аналізу ШІ: {str(e)}"

def get_work_ua():
    query = urllib.parse.quote("комерційний директор")
    url = f"https://www.work.ua/resumes-vinnytsya-{query}/"
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        
        data = ""
        for card in cards[:10]:
            link = card.find('a', href=True)
            info = card.find('p', class_='text-muted')
            if link:
                data += f"Кандидат: {link.get_text(strip=True)}\nДосвід: {info.get_text(strip=True) if info else ''}\nПосилання: https://www.work.ua{link['href']}\n\n"
        return data
    except: return ""

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Обрізаємо повідомлення, якщо воно занадто довге для Telegram
    requests.post(url, data={"chat_id": chat_id, "text": message[:4000], "parse_mode": "Markdown"})

if __name__ == "__main__":
    raw_candidates = get_work_ua()
    if raw_candidates:
        report = get_ai_analysis(raw_candidates)
        send_telegram(f"🤖 **Звіт ШІ-рекрутера (Хлібобулочні вироби):**\n\n{report}")
    else:
        send_telegram("📭 Нових резюме на Work.ua сьогодні не знайдено.")

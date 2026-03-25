import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

# --- 1. КРИТЕРІЇ ВІДБОРУ ---
AI_CRITERIA = """
Ти - рекрутер хлібозаводу (Вінниця). Шукаємо Керівника продажу/Комерційного директора.
Специфіка: FMCG (хліб). 
ЗАВДАННЯ: Проаналізуй список. Відсій тих, хто не з продуктів або без досвіду управління.
Напиши коротко: ✅ ПІБ - чому підходить - Посилання.
"""

def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "⚠️ Помилка: Немає API ключа."

    try:
        # ЗБІЛЬШЕНО ТАЙМАУТ до 60 секунд для стабільності
        timeout_val = 60 
        
        # КРОК 1: Отримуємо назву моделі автоматично
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_res = requests.get(list_url, timeout=timeout_val).json()
        
        # Вибираємо першу модель, що підтримує генерацію
        target_model = None
        if 'models' in list_res:
            for m in list_res['models']:
                if 'generateContent' in m['supportedGenerationMethods']:
                    target_model = m['name']
                    break
        
        if not target_model:
            return "❌ Не вдалося знайти робочу модель у вашому акаунті."

        # КРОК 2: Відправляємо запит на аналіз
        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати:\n{candidate_data}"}]}],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 1000, # Обмежуємо відповідь, щоб була швидшою
            }
        }
        
        r = requests.post(url, json=payload, timeout=timeout_val)
        res = r.json()
        
        if 'candidates' in res:
            return res['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"⚠️ Помилка відповіді від {target_model}: {res.get('error', {}).get('message', 'Unknown error')}"
            
    except requests.exceptions.Timeout:
        return "❌ Помилка: Google занадто довго думав (Таймаут). Спробуйте запустити ще раз."
    except Exception as e:
        return f"❌ Помилка: {str(e)}"

def get_work_ua():
    query = urllib.parse.quote("комерційний директор")
    url = f"https://www.work.ua/resumes-vinnytsya-{query}/"
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        data = ""
        for card in cards[:8]: # Зменшили до 8, щоб ШІ швидше обробляв
            link = card.find('a', href=True)
            info = card.find('p', class_='text-muted')
            if link:
                data += f"КАНДИДАТ: {link.get_text(strip=True)}\nІНФО: {info.get_text(strip=True) if info else ''}\nПОСИЛАННЯ: https://www.work.ua{link['href']}\n\n"
        return data
    except: return None

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    # Текстовий режим для кращої читаємості
    requests.post(url, data={"chat_id": chat_id, "text": message[:4000], "disable_web_page_preview": True})

if __name__ == "__main__":
    raw_candidates = get_work_ua()
    if raw_candidates:
        report = get_ai_analysis(raw_candidates)
        send_telegram(f"🤖 Звіт ШІ-рекрутера (Хлібозавод):\n\n{report}")
    else:
        send_telegram("📭 Нових резюме сьогодні не знайдено.")

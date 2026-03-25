import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

# --- 1. КРИТЕРІЇ ВІДБОРУ ---
AI_CRITERIA = """
Ти - рекрутер хлібозаводу у Вінницькій області. Шукаємо Керівника відділу продажу/Комерційного директора.
Специфіка: FMCG, продукти харчування (хліб).
ЗАВДАННЯ: Проаналізуй список. Відсій тих, хто не з продуктів або не має досвіду управління.
Напиши: ✅ ПІБ - чому підходить - Посилання.
"""

def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "⚠️ Помилка: Немає API ключа у Secrets."

    try:
        # КРОК 1: Питаємо у Google, які моделі нам доступні
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_res = requests.get(list_url, timeout=10).json()
        
        available_models = []
        if 'models' in list_res:
            # Шукаємо моделі, які вміють генерувати контент
            available_models = [m['name'] for m in list_res['models'] if 'generateContent' in m['supportedGenerationMethods']]
        
        if not available_models:
            return f"❌ Доступних моделей не знайдено. Відповідь API: {str(list_res)[:200]}"

        # КРОК 2: Беремо першу доступну модель (зазвичай це flash або pro)
        target_model = available_models[0]
        
        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати:\n{candidate_data}"}]}]
        }
        
        r = requests.post(url, json=payload, timeout=25)
        res = r.json()
        
        if 'candidates' in res:
            return res['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"⚠️ Модель {target_model} не повернула текст: {res.get('error', {}).get('message', 'Unknown error')}"
            
    except Exception as e:
        return f"❌ Помилка: {str(e)}"

def get_work_ua():
    query = urllib.parse.quote("комерційний директор")
    url = f"https://www.work.ua/resumes-vinnytsya-{query}/"
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        data = ""
        for card in cards[:10]:
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
    requests.post(url, data={"chat_id": chat_id, "text": message[:4000], "parse_mode": "Markdown", "disable_web_page_preview": True})

if __name__ == "__main__":
    raw_candidates = get_work_ua()
    if raw_candidates:
        report = get_ai_analysis(raw_candidates)
        send_telegram(f"🤖 **Звіт ШІ-рекрутера (Хлібозавод):**\n\n{report}")
    else:
        send_telegram("📭 Нових резюме сьогодні не знайдено.")

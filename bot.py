import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

# --- 1. КРИТЕРІЇ ВІДБОРУ (БІЛЬШ СУВОРІ) ---
AI_CRITERIA = """
Ти - рекрутер хлібозаводу (Вінниця). Шукаємо Керівника продажу/Комерційного директора.
Специфіка: FMCG (хліб, продукти харчування). 

ЗАВДАННЯ: 
1. Проаналізуй список резюме. 
2. Відсій тих, хто НЕ працював з продуктами харчування або НЕ має досвіду управління командою.
3. ВІДПОВІДАЙ СУВОРО за шаблоном для кожного підходящого:
✅ [ПІБ/Посада] - [Коротко: чому підходить] - [Посилання]

Якщо підходящих немає, напиши: "Сьогодні релевантних кандидатів не знайдено."
Не пиши вступних фраз на кшталт "Я проаналізував...". Тільки список.
"""

def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "⚠️ Помилка: Немає API ключа."

    try:
        timeout_val = 60 
        # Автопідбір моделі
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_res = requests.get(list_url, timeout=timeout_val).json()
        
        target_model = None
        if 'models' in list_res:
            for m in list_res['models']:
                if 'generateContent' in m['supportedGenerationMethods']:
                    target_model = m['name']
                    break
        
        if not target_model: return "❌ Робочу модель не знайдено."

        # Аналіз
        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати для аналізу:\n{candidate_data}"}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 1500}
        }
        
        r = requests.post(url, json=payload, timeout=timeout_val)
        res = r.json()
        
        if 'candidates' in res:
            return res['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"⚠️ Помилка ШІ: {res.get('error', {}).get('message', 'Немає відповіді')}"
            
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
    requests.post(url, data={"chat_id": chat_id, "text": message[:4000], "disable_web_page_preview": True})

if __name__ == "__main__":
    raw_candidates = get_work_ua()
    if raw_candidates:
        report = get_ai_analysis(raw_candidates)
        send_telegram(f"🤖 **Звіт ШІ-рекрутера:**\n\n{report}")
    else:
        send_telegram("📭 Сьогодні на Work.ua нових кандидатів не знайдено.")

import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

# --- 1. КРИТЕРІЇ ВІДБОРУ ---
AI_CRITERIA = """
Ти - рекрутер хлібозаводу у Вінницькій області. Шукаємо Керівника відділу продажу/Комерційного директора.
Специфіка: FMCG, продукти харчування (хліб).
КРИТЕРІЇ: Досвід у продуктах харчування, управління командою, знання Вінниччини.
ЗАВДАННЯ: Проаналізуй список. Відсій невідповідних. Для підходящих напиши: ✅ ПІБ - чому підходить - Посилання.
"""

# --- 2. ФУНКЦІЯ АНАЛІЗУ З АВТО-ПІДБОРОМ МОДЕЛІ ---
def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "⚠️ Помилка: Немає API ключа."

    # Список моделей для спроб (від найновішої до стабільної)
    models_to_try = ["gemini-1.5-flash-latest", "gemini-1.5-flash", "gemini-pro"]
    
    last_error = ""
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати:\n{candidate_data}"}]}],
            "safetySettings": [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"}]
        }
        
        try:
            r = requests.post(url, json=payload, timeout=25)
            res = r.json()
            if 'candidates' in res:
                return res['candidates'][0]['content']['parts'][0]['text']
            last_error = res.get('error', {}).get('message', 'Unknown error')
        except Exception as e:
            last_error = str(e)
            continue
            
    return f"❌ Жодна модель не спрацювала. Остання помилка: {last_error}"

# --- 3. ПАРСИНГ WORK.UA ---
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

# --- 4. TELEGRAM ---
def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message[:4000], "parse_mode": "Markdown", "disable_web_page_preview": True})

if __name__ == "__main__":
    raw = get_work_ua()
    if raw:
        report = get_ai_analysis(raw)
        send_telegram(f"🤖 **Звіт ШІ-рекрутера (Хлібозавод):**\n\n{report}")
    else:
        send_telegram("📭 Нових кандидатів не знайдено.")

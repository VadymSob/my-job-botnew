import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. НАЛАШТУВАННЯ ПОШУКУ ---
QUERIES = {
    "💼 КОМЕРЦІЙНИЙ ДИРЕКТОР": ["комерційний директор", "commercial director"],
    "🏗️ НАЧАЛЬНИК ВИРОБНИЦТВА": ["начальник виробництва хліб", "керівник хлібопекарського виробництва"],
    "🧪 ТЕХНОЛОГ": ["технолог хлібобулочних", "головний технолог хліб"]
}
LOCATIONS = ["ukraine", "vinnytsya"]
DB_FILE = "processed_resumes.txt"

# --- 2. СУВОРИЙ ФІЛЬТР ---
AI_CRITERIA = """
Ти - професійний рекрутер хлібозаводу. Проаналізуй досвід кандидата.
Шукаємо фахівців саме для ХЛІБОПЕКАРСЬКОЇ або ХАРЧОВОЇ галузі.

КАТЕГОРІЇ:
⭐ СУПЕР ПРІОРИТЕТ: Прямий досвід у хлібі/булочках/випічці.
✅ ПРІОРИТЕТ: Досвід у харчовому виробництві (м'ясо, молоко, кондитерка).
❌ ВІДМОВА: Досвід в IT, авто, будівництві, фармації або металургії.

ПРАВИЛО: Якщо немає харчового досвіду — ПИШИ ❌. Не вигадуй компанії!
Формат: [Результат] - [Посада] - [Компанія/Досвід] - [Посилання]
"""

def get_processed_links():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_links(links):
    if not links: return
    with open(DB_FILE, "a") as f:
        for link in links: f.write(link + "\n")

def get_active_model(api_key):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        res = requests.get(url, timeout=30).json()
        return next((m['name'] for m in res.get('models', []) if 'generateContent' in m['supportedGenerationMethods']), "models/gemini-1.5-flash")
    except: return "models/gemini-1.5-flash"

def get_ai_analysis(batch_text, model_name):
    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nСписок:\n{batch_text}"}]}],
        "generationConfig": {"temperature": 0.0}
    }
    try:
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        return res['candidates'][0]['content']['parts'][0]['text'] if 'candidates' in res else None
    except: return None

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id or not message.strip(): return
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True})

def process_category(category_name, search_queries, model_name, processed):
    all_found = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for q in search_queries:
        for loc in LOCATIONS:
            url = f"https://www.work.ua/resumes-{loc}-{urllib.parse.quote(q)}/?days=7"
            try:
                r = requests.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(r.text, 'html.parser')
                cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
                for card in cards[:10]:
                    link = "https://www.work.ua" + card.find('a', href=True)['href'].split('?')[0]
                    if link not in processed:
                        text = card.get_text(" ", strip=True)
                        all_found.append(f"ДАНІ: {text}\nПосилання: {link}")
                        processed.add(link)
                time.sleep(1)
            except: continue
            
    if all_found:
        # Аналізуємо пачками по 5, щоб ШІ не помилявся
        for i in range(0, len(all_found), 5):
            batch = "\n---\n".join(all_found[i:i+5])
            report = get_ai_analysis(batch, model_name)
            if report:
                send_telegram(f"📌 **{category_name}** (Група {i//5 + 1}):\n\n{report}")
            time.sleep(20) # Пауза для лімітів Google
        return [f.split("Посилання: ")[1] for f in all_found]
    return []

if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY")
    active_model = get_active_model(api_key)
    processed = get_processed_links()
    total_new_links = []

    print(f"Запуск. Використовуємо модель: {active_model}")

    for cat_name, queries in QUERIES.items():
        print(f"Шукаю: {cat_name}...")
        new_links = process_category(cat_name, queries, active_model, processed)
        total_new_links.extend(new_links)

    if total_new_links:
        save_processed_links(total_new_links)
        print(f"Готово. Знайдено та оброблено: {len(total_new_links)}")
    else:
        print("Нових резюме немає.")

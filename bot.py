import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. НАЛАШТУВАННЯ ПОШУКУ ---
QUERIES = {
    "💼 КОМЕРЦІЙНИЙ ДИРЕКТОР": ["комерційний директор", "commercial director"],
    "🏗️ НАЧАЛЬНИК ВИРОБНИЦТВА": ["начальник виробництва хліб", "керівник хлібопекарського виробництва"],
    "🧪 ТЕХНОЛОГ": ["технолог хлібобулочних", "головний технолог хліб"],
    "🚚 ЛОГІСТ (Транспорт)": ["логіст транспортний", "диспетчер логіст", "менеджер з логістики"]
}
LOCATIONS = ["ukraine"]
DB_FILE = "processed_resumes.txt"

# --- 2. РОЗШИРЕНИЙ ФІЛЬТР ---
AI_CRITERIA = """
Ти - рекрутер хлібозаводу у Вінниці. Проаналізуй досвід та локацію кандидата.
Вимоги:
1. КОМЕРЦІЙНИЙ/ВИРОБНИЦТВО/ТЕХНОЛОГ: Пріоритет - харчова сфера (хліб, м'ясо, молоко).
2. ЛОГІСТ: Транспортна логістика, маршрути (Вінниця/область), контроль GPS, власний автопарк.
КЛАСИФІКАЦІЯ:
⭐ СУПЕР ПРІОРИТЕТ: Відповідний досвід + Вінниця (або готовність до переїзду).
✅ ПРІОРИТЕТ: Харчовий досвід/Логістика FMCG + готовність до переїзду.
❌ ВІДМОВА: Немає досвіду маршрутизації/харчового досвіду АБО не готовий до переїзду.
Формат: [Результат] - [Вакансія] - [Місто/Переїзд] - [Досвід] - [Посилання]
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
    payload = {"contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nСписок кандидатів:\n{batch_text}"}]}], "generationConfig": {"temperature": 0.0}}
    try:
        r = requests.post(url, json=payload, timeout=60)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except: return None

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id or not message.strip(): return
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True})

def process_category(category_name, search_queries, model_name, processed):
    category_links = []
    candidates_to_analyze = []
    # Імітуємо реальний браузер
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    for q in search_queries:
        url = f"https://www.work.ua/resumes-ukraine-{urllib.parse.quote(q)}/?days=30"
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code != 200:
                print(f"Помилка доступу до Work.ua: {r.status_code}")
                continue
            
            soup = BeautifulSoup(r.text, 'html.parser')
            # Work.ua часто змінює класи, шукаємо по декількох ознаках
            cards = soup.find_all('div', class_=['card', 'card-hover', 'resume-link'])
            if not cards:
                # Спробуємо знайти по іншому селектору
                cards = soup.select('div.card.card-resumes')

            for card in cards[:30]:
                link_tag = card.find('a', href=True)
                if link_tag and '/resumes/' in link_tag['href']:
                    link = "https://www.work.ua" + link_tag['href'].split('?')[0]
                    if link not in processed:
                        info = card.get_text(" ", strip=True)
                        candidates_to_analyze.append(f"ДАНІ: {info}\nПосилання: {link}")
                        category_links.append(link)
            time.sleep(2) # Пауза між запитами до сайту
        except Exception as e:
            print(f"Помилка на запиті {q}: {e}")
    
    if candidates_to_analyze:
        print(f"Знайдено {len(candidates_to_analyze)} нових для {category_name}. Аналізую...")
        for i in range(0, len(candidates_to_analyze), 5):
            batch = "\n---\n".join(candidates_to_analyze[i:i+5])
            report = get_ai_analysis(batch, model_name)
            if report:
                send_telegram(f"🔍 **ГЛОБАЛЬНО (30 днів): {category_name}**\n\n{report}")
            time.sleep(25)
    return category_links

if __name__ == "__main__":
    api_key = os.getenv("GEMINI_API_KEY")
    active_model = get_active_model(api_key)
    processed = get_processed_links()
    all_new = []

    for cat_name, queries in QUERIES.items():
        print(f"Пошук {cat_name}...")
        res = process_category(cat_name, queries, active_model, processed)
        all_new.extend(res)
        processed.update(res)

    if all_new:
        save_processed_links(all_new)
        print(f"Завершено. Оброблено: {len(all_new)}")
    else:
        print("Нікого не знайдено. Можливо, сайт тимчасово обмежив доступ.")

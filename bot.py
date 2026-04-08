import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time
import random

QUERIES = {
    "💼 КОМЕРЦІЙНИЙ ДИРЕКТОР": ["комерційний директор", "commercial director"],
    "🏗️ НАЧАЛЬНИК ВИРОБНИЦТВА": ["начальник виробництва хліб", "керівник хлібопекарського виробництва"],
    "🧪 ТЕХНОЛОГ": ["технолог хлібобулочних", "головний технолог хліб"],
    "🚚 ЛОГІСТ (Транспорт)": ["логіст транспортний", "диспетчер логіст", "менеджер з логістики"]
}
DB_FILE = "processed_resumes.txt"

def get_processed_links():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_links(links):
    if not links: return
    with open(DB_FILE, "a") as f:
        for link in links: f.write(link + "\n")

def get_ai_analysis(batch_text):
    api_key = os.getenv("GEMINI_API_KEY")
    # Спробуємо спрощений URL без вибору моделі вручну для стабільності
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": f"Ти рекрутер. Оціни кандидатів для хлібозаводу у Вінниці. Хто підходить (харчовий досвід/логістика/переїзд) - пиши категорію та посилання. Хто ні - ❌.\n\n{batch_text}"}]}]}
    try:
        r = requests.post(url, json=payload, timeout=60)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except: return None

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True})

def process():
    processed = get_processed_links()
    all_new = []
    user_cookie = os.getenv("WORK_UA_COOKIE", "")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/",
        "Cookie": user_cookie
    }

    for cat_name, queries in QUERIES.items():
        cat_candidates = []
        print(f"Пошук {cat_name}...")
        for q in queries:
            url = f"https://www.work.ua/resumes-ukraine-{urllib.parse.quote(q)}/?days=30"
            try:
                # Додаємо випадкову затримку, щоб імітувати людину
                time.sleep(random.randint(5, 15))
                r = requests.get(url, headers=headers, timeout=30)
                
                if r.status_code != 200:
                    print(f"Сторінку не знайдено (код {r.status_code})")
                    continue

                soup = BeautifulSoup(r.text, 'html.parser')
                # Шукаємо всі посилання, що містять '/resumes/'
                links_on_page = soup.find_all('a', href=True)
                
                for a in links_on_page:
                    href = a['href']
                    if '/resumes/' in href and href.count('/') >= 3:
                        full_link = "https://www.work.ua" + href.split('?')[0]
                        if full_link not in processed and full_link not in [c.split('\n')[1] for c in cat_candidates if '\n' in c]:
                            # Спробуємо взяти текст батьківського елемента (картки)
                            parent_text = a.find_parent('div').get_text(" ", strip=True) if a.find_parent('div') else "Резюме"
                            if len(parent_text) > 100:
                                cat_candidates.append(f"ДАНІ: {parent_text}\n{full_link}")
                                processed.add(full_link)
                                all_new.append(full_link)
            except Exception as e:
                print(f"Помилка: {e}")

        if cat_candidates:
            for i in range(0, len(cat_candidates), 5):
                batch = "\n---\n".join(cat_candidates[i:i+5])
                res = get_ai_analysis(batch)
                if res:
                    send_telegram(f"🔍 {cat_name} (30 днів):\n\n{res}")
                time.sleep(20)

    if all_new:
        save_processed_links(all_new)
        print(f"Успіх! Знайдено: {len(all_new)}")
    else:
        print("Нікого не знайдено. Work.ua все ще блокує або немає нових резюме.")

if __name__ == "__main__":
    process()

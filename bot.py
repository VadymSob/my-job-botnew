import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time
import random

# --- 1. НАЛАШТУВАННЯ ---
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

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if token and chat_id:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}
        try: requests.post(url, data=data, timeout=30)
        except: pass

def get_ai_analysis(batch_text):
    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = (
        "Ти професійний рекрутер. Оціни резюме для хлібозаводу у Вінниці. "
        "Шукаємо: харчовий досвід (хліб/молоко/м'ясо) або логістів з маршрутами та GPS. "
        "Обов'язково: локація Вінниця або готовність до переїзду. "
        "Формат: [Пріоритет] - [Посада] - [Місто/Переїзд] - [Посилання].\n\n"
        f"{batch_text}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        return res['candidates'][0]['content']['parts'][0]['text'] if 'candidates' in res else None
    except: return None

def process():
    print("🚀 Старт посиленого пошуку...")
    processed = get_processed_links()
    all_new_links = []
    
    # Використовуємо ваші точні куки та заголовки
    user_cookie = os.getenv("WORK_UA_COOKIE", "")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.7680.178 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie": user_cookie,
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-platform": '"Windows"',
        "referer": "https://www.work.ua/resumes/",
        "cache-control": "max-age=0"
    }

    for cat_name, queries in QUERIES.items():
        cat_candidates = []
        for q in queries:
            search_url = f"https://www.work.ua/resumes-ukraine-{urllib.parse.quote(q)}/?days=30"
            try:
                time.sleep(random.randint(10, 20)) # Збільшена пауза для безпеки
                r = requests.get(search_url, headers=headers, timeout=30)
                
                if "robot" in r.text.lower() or r.status_code == 403:
                    print(f"❌ Заблоковано для {q}")
                    continue

                soup = BeautifulSoup(r.text, 'html.parser')
                # Шукаємо посилання на резюме
                links = soup.select('h2 a[href^="/resumes/"], div.card a[href^="/resumes/"]')
                
                for a in links:
                    href = a['href'].split('?')[0]
                    full_link = "https://www.work.ua" + href
                    if full_link not in processed:
                        # Беремо текст картки
                        card = a.find_parent('div', class_='card') or a.find_parent('div')
                        txt = card.get_text(" ", strip=True)[:600] if card else "Кандидат"
                        cat_candidates.append(f"ДАНІ: {txt}\n{full_link}")
                        processed.add(full_link)
                        all_new_links.append(full_link)
                        print(f"Знайдено: {full_link}")
            except Exception as e:
                print(f"Помилка: {e}")

        if cat_candidates:
            for i in range(0, len(cat_candidates), 5):
                batch = "\n---\n".join(cat_candidates[i:i+5])
                report = get_ai_analysis(batch)
                if report:
                    send_telegram(f"🔍 **{cat_name} (30 днів):**\n\n{report}")
                else:
                    # Резервна відправка посилань
                    links_text = "\n".join([c.split('\n')[-1] for c in cat_candidates[i:i+5]])
                    send_telegram(f"📎 **{cat_name} (Нові посилання):**\n{links_text}")
                time.sleep(20)

    if all_new_links:
        save_processed_links(all_new_links)
        send_telegram(f"✅ Успіх! Оброблено {len(all_new_links)} резюме за місяць.")
    else:
        print("Нічого не знайдено.")

if __name__ == "__main__":
    process()

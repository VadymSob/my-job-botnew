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
        try:
            requests.post(url, data=data, timeout=30)
        except:
            pass

def get_ai_analysis(batch_text):
    api_key = os.getenv("GEMINI_API_KEY")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    prompt = (
        "Ти професійний рекрутер. Проаналізуй список резюме нижче. "
        "Для кожної посади виділи тільки тих, хто має досвід у харчовій галузі (хліб, молоко, м'ясо тощо) "
        "або логістиці маршрутів, та вказав готовність до переїзду у Вінницю (або вже там). "
        "Формат: [Пріоритет] - [Посада] - [Компанія] - [Посилання]. "
        "Якщо кандидат не підходить, просто не пиши про нього.\n\n"
        f"{batch_text}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    try:
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        if 'candidates' in res:
            return res['candidates'][0]['content']['parts'][0]['text']
    except:
        return None
    return None

def process():
    send_telegram("🚀 Бот розпочав масштабний пошук (30 днів)...")
    processed = get_processed_links()
    all_new_links = []
    user_cookie = os.getenv("WORK_UA_COOKIE", "")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie": user_cookie,
        "Referer": "https://www.work.ua/"
    }

    for cat_name, queries in QUERIES.items():
        cat_candidates = []
        print(f"Пошук у категорії: {cat_name}")
        
        for q in queries:
            # Масштабний пошук: 30 днів
            search_url = f"https://www.work.ua/resumes-ukraine-{urllib.parse.quote(q)}/?days=30"
            try:
                time.sleep(random.randint(8, 15))
                r = requests.get(search_url, headers=headers, timeout=30)
                
                if r.status_code != 200:
                    print(f"⚠️ Помилка {r.status_code} для запиту {q}")
                    continue

                if "robot" in r.text.lower() or "зупиніться" in r.text.lower():
                    print(f"❌ Капча виявлена для {q}. Оновіть Cookie.")
                    send_telegram(f"❌ Work.ua заблокував запит за ключем '{q}'. Потрібні свіжі Cookie!")
                    continue

                soup = BeautifulSoup(r.text, 'html.parser')
                
                # Пошук посилань: спочатку за заголовками, потім загальний
                found_links = soup.select('h2 a[href^="/resumes/"]')
                if not found_links:
                    found_links = [a for a in soup.find_all('a', href=True) if '/resumes/' in a['href'] and len(a['href']) > 15]

                for a in found_links:
                    href = a['href'].split('?')[0]
                    full_link = "https://www.work.ua" + href
                    
                    if full_link not in processed:
                        # Намагаємось знайти текст навколо посилання
                        card = a.find_parent('div', class_='card') or a.find_parent('div')
                        snippet = card.get_text(" ", strip=True)[:600] if card else "Текст резюме"
                        
                        cat_candidates.append(f"ДАНІ: {snippet}\n{full_link}")
                        processed.add(full_link)
                        all_new_links.append(full_link)
                        print(f"Знайдено нове: {full_link}")
            except Exception as e:
                print(f"Помилка при обробці {q}: {e}")

        # Якщо знайшли нових людей у категорії - аналізуємо та звітуємо
        if cat_candidates:
            print(f"Аналізую {len(cat_candidates)} кандидатів у {cat_name}...")
            for i in range(0, len(cat_candidates), 5):
                batch = "\n---\n".join(cat_candidates[i:i+5])
                report = get_ai_analysis(batch)
                
                if report and len(report.strip()) > 10:
                    send_telegram(f"📌 **{cat_name}** (Знайдено {len(cat_candidates)}):\n\n{report}")
                else:
                    # Якщо ШІ нікого не відібрав або помилився, скидаємо посилання списком
                    links_list = "\n".join([c.split('\n')[-1] for c in cat_candidates[i:i+5]])
                    send_telegram(f"📎 **{cat_name}** (Нові посилання):\n{links_list}")
                time.sleep(20)

    if all_new_links:
        save_processed_links(all_new_links)
        print(f"Успіх! Оброблено {len(all_new_links)} резюме.")
        send_telegram(f"✅ Пошук завершено. Оброблено нових резюме: {len(all_new_links)}")
    else:
        print("Нових резюме не знайдено.")
        send_telegram("📭 Нових резюме за 30 днів не знайдено (або спрацював захист сайту).")

if __name__ == "__main__":
    process()

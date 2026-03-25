import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- НАЛАШТУВАННЯ ---
QUERIES = ["комерційний директор", "commercial director"]
LOCATIONS = ["ukraine", "vinnytsya"]
DB_FILE = "processed_resumes.txt"

AI_CRITERIA = """
Ти - рекрутер. Проаналізуй список кандидатів.
Шукаємо: Комерційний директор (Скоропорт/Харчова сфера).
Для кожного підходящого напиши: ✅ [Посада] - [Чому підходить] - [Посилання]
Для інших: ❌ [Посада] - [Сфера] - [Посилання]
"""

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
    # Використовуємо стабільну модель
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nСписок:\n{batch_text}"}]}]}
    
    try:
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        if 'candidates' in res:
            return res['candidates'][0]['content']['parts'][0]['text']
        else:
            # Якщо квота вичерпана, виводимо помилку
            print(f"DEBUG: Помилка ШІ: {res.get('error', {}).get('message', 'Невідома помилка')}")
            return None
    except: return None

def get_work_ua_data():
    processed = get_processed_links()
    all_candidates = []
    new_links = []
    headers = {"User-Agent": "Mozilla/5.0"}
    
    for loc in LOCATIONS:
        for q in QUERIES:
            url = f"https://www.work.ua/resumes-{loc}-{urllib.parse.quote(q)}/?days=122"
            try:
                r = requests.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(r.text, 'html.parser')
                cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
                for card in cards[:15]:
                    link = "https://www.work.ua" + card.find('a', href=True)['href'].split('?')[0]
                    if link not in processed:
                        title = card.find('a').get_text(strip=True)
                        desc = card.find('p', class_='text-muted').get_text(strip=True) if card.find('p', class_='text-muted') else ""
                        all_candidates.append(f"Посада: {title}\nДосвід: {desc}\nПосилання: {link}")
                        new_links.append(link)
                        processed.add(link)
            except: continue
    return all_candidates, new_links

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id or not message: return
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True})

if __name__ == "__main__":
    candidates, links = get_work_ua_data()
    if candidates:
        # Пакетна обробка по 7 кандидатів, щоб не "вбивати" квоту запитами
        for i in range(0, len(candidates), 7):
            batch = "\n\n".join(candidates[i:i+7])
            report = get_ai_analysis(batch)
            if report:
                send_telegram(f"👔 Звіт (Група {i//7 + 1}):\n\n{report}")
            time.sleep(10) # Пауза між групами
        save_processed_links(links)

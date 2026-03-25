import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. ПАРАМЕТРИ ---
QUERIES = ["комерційний директор", "директор хлібзаводу", "керівник відділу продажу"]
LOCATIONS = ["ukraine", "vinnytsya"]
MAX_PAGES = 2 # 2 сторінки достатньо, щоб не "заспамити" ШІ
DB_FILE = "processed_resumes.txt"

AI_CRITERIA = """
Ти - рекрутер хлібозаводу. Шукаємо ТОП-менеджера.
ПРІОРИТЕТ: Досвід на ХЛІБОЗАВОДАХ, хлібокомбінатах, КХП, м'ясокомбінатах, молочці (FMCG Food).
ФОРМАТ: ✅ [ПІБ/Посада] - [Чому підходить] - [Посилання]
Якщо в списку немає релевантних, просто нічого не пиши.
"""

def get_processed_links():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_links(links):
    if not links: return
    with open(DB_FILE, "a") as f:
        for link in links: f.write(link + "\n")

def get_ai_analysis(candidate_batch):
    api_key = os.getenv("GEMINI_API_KEY")
    try:
        # Авто-вибір моделі
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_res = requests.get(list_url, timeout=30).json()
        target_model = next((m['name'] for m in list_res.get('models', []) if 'generateContent' in m['supportedGenerationMethods']), "models/gemini-1.5-flash")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати:\n{candidate_batch}"}]}]}
        
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        if 'candidates' in res:
            return res['candidates'][0]['content']['parts'][0]['text']
    except: return None
    return None

def get_work_ua_data():
    processed = get_processed_links()
    all_candidates = []
    new_links_to_save = []
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    
    for loc in LOCATIONS:
        for q in QUERIES:
            for page in range(1, MAX_PAGES + 1):
                url = f"https://www.work.ua/resumes-{loc}-{urllib.parse.quote(q)}/?days=122&page={page}"
                try:
                    r = requests.get(url, headers=headers, timeout=20)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
                    if not cards: break
                    
                    for card in cards:
                        link_tag = card.find('a', href=True)
                        if link_tag:
                            link = "https://www.work.ua" + link_tag['href'].split('?')[0]
                            if link not in processed:
                                name = link_tag.get_text(strip=True)
                                info = card.find('p', class_='text-muted')
                                all_candidates.append(f"КАНДИДАТ: {name}\nІНФО: {info.get_text(strip=True) if info else ''}\nПОСИЛАННЯ: {link}")
                                new_links_to_save.append(link)
                    time.sleep(1)
                except: continue
    return all_candidates, new_links_to_save

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id or not message.strip(): return
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True})

if __name__ == "__main__":
    candidates, links = get_work_ua_data()
    
    if candidates:
        # Розбиваємо 56 кандидатів на групи по 10 осіб
        batch_size = 10
        for i in range(0, len(candidates), batch_size):
            batch = "\n\n".join(candidates[i:i+batch_size])
            report = get_ai_analysis(batch)
            if report and len(report) > 10:
                send_telegram(f"🤖 **Звіт ШІ (Частина {i//batch_size + 1}):**\n\n{report}")
            time.sleep(2) # Пауза між запитами до ШІ
            
        save_processed_links(links)
    else:
        print("Нічого нового.")

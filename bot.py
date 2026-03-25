import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- НАЛАШТУВАННЯ ---
QUERIES = ["комерційний директор"]
LOCATIONS = ["ukraine", "vinnytsya"]
DB_FILE = "processed_resumes.txt"

# Полегшений промпт для обходу фільтрів безпеки ШІ
AI_CRITERIA = """
Ти - асистент рекрутера. Перед тобою список кандидатів.
Твоє завдання: позначити тих, хто працював у харчовій промисловості (хліб, м'ясо, молоко, продукти).

Для кожного напиши:
✅ [Посада] - [Компанія/Сфера] - [Посилання]
Якщо сфера не харчова (IT, будівництво тощо), напиши:
❌ [Посада] - [Сфера] - [Посилання]

Пиши коротко, без вступу.
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
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nСписок:\n{candidate_batch}"}]}],
        "generationConfig": {"temperature": 0.1}
    }
    
    try:
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        if 'candidates' in res and 'content' in res['candidates'][0]:
            return res['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"DEBUG: ШІ не дав результату. Відповідь: {res}")
            return None
    except Exception as e:
        print(f"DEBUG: Помилка запиту до ШІ: {e}")
        return None

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
                
                for card in cards[:20]: # Беремо перші 20 для тесту
                    link_tag = card.find('a', href=True)
                    if link_tag:
                        link = "https://www.work.ua" + link_tag['href'].split('?')[0]
                        if link not in processed:
                            title = link_tag.get_text(strip=True)
                            desc = card.find('p', class_='text-muted')
                            desc_text = desc.get_text(strip=True) if desc else "Немає опису"
                            
                            all_candidates.append(f"Посада: {title}\nДосвід: {desc_text}\nПосилання: {link}")
                            new_links.append(link)
                            processed.add(link)
                time.sleep(1)
            except: continue
    return all_candidates, new_links

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id: return
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": message[:4000], "disable_web_page_preview": True})

if __name__ == "__main__":
    candidates, links = get_work_ua_data()
    if candidates:
        print(f"Знайдено кандидатів: {len(candidates)}. Надсилаю на аналіз...")
        
        # Обробка групами по 10
        for i in range(0, len(candidates), 10):
            batch = "\n\n".join(candidates[i:i+10])
            report = get_ai_analysis(batch)
            
            if report:
                print(f"--- ЗВІТ ШІ (Частина {i//10 + 1}) ---\n{report}\n")
                send_telegram(f"🔍 Звіт {i//10 + 1}:\n\n{report}")
            else:
                print(f"Група {i//10 + 1}: ШІ нічого не повернув.")
        
        save_processed_links(links)
    else:
        print("Нових записів немає.")

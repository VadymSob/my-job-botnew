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
Ти - рекрутер. Стисло проаналізуй досвід. 
Шукаємо: Комерційний директор (Харчова промисловість/Скоропорт/FMCG).
Формат:
✅ [Посада] - [Коротко досвід] - [Посилання]
❌ [Посада] - [Сфера/Причина] - [Посилання]
"""

def get_processed_links():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f: return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_links(links):
    if not links: return
    with open(DB_FILE, "a") as f:
        for link in links: f.write(link + "\n")

def get_ai_analysis(candidate_single):
    api_key = os.getenv("GEMINI_API_KEY")
    try:
        # Авто-вибір моделі через сервісний запит
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        models_res = requests.get(list_url, timeout=30).json()
        active_model = next((m['name'] for m in models_res.get('models', []) 
                            if 'generateContent' in m['supportedGenerationMethods']), "models/gemini-1.5-flash")

        url = f"https://generativelanguage.googleapis.com/v1beta/{active_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидат:\n{candidate_single}"}]}],
            "generationConfig": {"temperature": 0.1}
        }
        
        # 120 секунд для ОДНОГО кандидата - це з головою
        r = requests.post(url, json=payload, timeout=120)
        res = r.json()
        if 'candidates' in res:
            return res['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        print(f"DEBUG Помилка на одному кандидаті: {e}")
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
                
                for card in cards[:15]: # Беремо 15 найсвіжіших
                    link_tag = card.find('a', href=True)
                    if link_tag:
                        link = "https://www.work.ua" + link_tag['href'].split('?')[0]
                        if link not in processed:
                            title = link_tag.get_text(strip=True)
                            desc = card.find('p', class_='text-muted')
                            desc_text = desc.get_text(strip=True) if desc else ""
                            all_candidates.append(f"Посада: {title}\nДосвід: {desc_text}\nПосилання: {link}")
                            new_links.append(link)
                            processed.add(link)
                time.sleep(1)
            except: continue
    return all_candidates, new_links

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id or not message.strip(): return
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True})

if __name__ == "__main__":
    candidates, links = get_work_ua_data()
    if candidates:
        print(f"Знайдено: {len(candidates)}. Аналізую по одному...")
        
        # Аналіз кожного кандидата ОКРЕМО
        for i, cand in enumerate(candidates):
            report = get_ai_analysis(cand)
            if report:
                send_telegram(f"👤 Кандидат {i+1} з {len(candidates)}:\n\n{report}")
                print(f"Кандидат {i+1} оброблений.")
            
            # Невелика пауза між запитами до Google API (3-4 секунди)
            time.sleep(4) 
            
        save_processed_links(links)
        print("Всі кандидати оброблені.")
    else:
        print("Нових кандидатів немає.")

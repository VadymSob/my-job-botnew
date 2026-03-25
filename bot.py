import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- НАЛАШТУВАННЯ ---
QUERIES = ["комерційний директор", "commercial director"]
LOCATIONS = ["ukraine", "vinnytsya"]
DB_FILE = "processed_resumes.txt"

# Максимально простий промпт
AI_CRITERIA = "Проаналізуй досвід кандидата. Напиши: ✅ якщо підходить (скоропорт/харчова сфера) або ❌ якщо ні. Додай коротку причину та посилання."

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
        # Авто-вибір моделі
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        models_res = requests.get(list_url, timeout=30).json()
        active_model = next((m['name'] for m in models_res.get('models', []) 
                            if 'generateContent' in m['supportedGenerationMethods']), "models/gemini-1.5-flash")

        url = f"https://generativelanguage.googleapis.com/v1beta/{active_model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидат:\n{candidate_single}"}]}]}
        
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        
        if 'candidates' in res and 'content' in res['candidates'][0]:
            return res['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"DEBUG: ШІ промовчав. Відповідь: {res}")
            return f"⚠️ ШІ не зміг проаналізувати посилання: {candidate_single.split('Посилання: ')[-1]}"
    except Exception as e:
        print(f"DEBUG: Помилка: {e}")
        return None

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id or not message: return
    
    # ДУБЛЮЄМО В ЛОГИ, щоб бачити, що МАЛО піти в ТГ
    print(f"--- НАДСИЛАЮ В TG ---\n{message}\n--------------------")
    
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True})
    if r.status_code != 200:
        print(f"DEBUG: Помилка Telegram: {r.text}")

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
                
                for card in cards[:10]: # Обмежимо до 10 для стабільності
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

if __name__ == "__main__":
    candidates, links = get_work_ua_data()
    if candidates:
        print(f"Знайдено: {len(candidates)}. Аналізую...")
        for cand in candidates:
            report = get_ai_analysis(cand)
            if report:
                send_telegram(report)
            time.sleep(3) # Пауза
        save_processed_links(links)
    else:
        print("Нових немає.")

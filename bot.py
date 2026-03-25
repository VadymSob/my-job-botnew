import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- НАЛАШТУВАННЯ ПОШУКУ ---
QUERIES = ["комерційний директор", "commercial director"]
LOCATIONS = ["ukraine", "vinnytsya"]
DB_FILE = "processed_resumes.txt"

AI_CRITERIA = """
Ти - рекрутер. Познач тих, хто працював у харчовій промисловості (хліб, м'ясо, молоко, продукти, FMCG Food).
✅ [Посада] - [Компанія/Сфера] - [Посилання]
❌ [Посада] - [Сфера] - [Посилання]
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
        # 1. Запитуємо список доступних моделей, щоб не вгадувати назву
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        models_res = requests.get(list_url).json()
        
        # Шукаємо будь-яку модель, що підтримує генерацію контенту (flash або pro)
        active_model = next((m['name'] for m in models_res.get('models', []) 
                            if 'generateContent' in m['supportedGenerationMethods']), None)
        
        if not active_model:
            print("DEBUG: Не знайдено жодної доступної моделі в API.")
            return None

        # 2. Відправляємо запит до знайденої моделі
        url = f"https://generativelanguage.googleapis.com/v1beta/{active_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nСписок:\n{candidate_batch}"}]}],
            "generationConfig": {"temperature": 0.1}
        }
        
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        if 'candidates' in res:
            return res['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"DEBUG: Помилка генерації. Відповідь: {res}")
            return None
    except Exception as e:
        print(f"DEBUG: Виняток: {e}")
        return None

def get_work_ua_data():
    processed = get_processed_links()
    all_candidates = []
    new_links = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    for loc in LOCATIONS:
        for q in QUERIES:
            url = f"https://www.work.ua/resumes-{loc}-{urllib.parse.quote(q)}/?days=122"
            try:
                r = requests.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(r.text, 'html.parser')
                cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
                
                for card in cards[:15]:
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
    if not token or not chat_id: return
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                  data={"chat_id": chat_id, "text": message[:4000], "disable_web_page_preview": True})

if __name__ == "__main__":
    candidates, links = get_work_ua_data()
    if candidates:
        print(f"Знайдено: {len(candidates)}. Визначаю активну модель та аналізую...")
        for i in range(0, len(candidates), 10):
            batch = "\n\n".join(candidates[i:i+10])
            report = get_ai_analysis(batch)
            if report:
                send_telegram(f"👔 Звіт (Скоропорт):\n\n{report}")
            else:
                print("ШІ не зміг дати відповідь.")
        save_processed_links(links)
    else:
        print("Нових немає.")

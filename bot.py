import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. ПАРАМЕТРИ ПОШУКУ ---
QUERIES = ["комерційний директор", "commercial director"]
LOCATIONS = ["ukraine", "vinnytsya"]
DB_FILE = "processed_resumes.txt"

AI_CRITERIA = """
Ти - технічний фільтр резюме. Твоє завдання - відібрати тільки тих, хто має досвід у КОМЕРЦІЙНОМУ управлінні СКОРОПОРТНИМИ продуктами (FMCG Food: хліб, м'ясо, молоко, кондитерка).

СУВОРІ ПРАВИЛА:
1. ЗАБОРОНЕНО вигадувати імена, прізвища або факти. Використовуй тільки той текст, що надано.
2. ПРІОРИТЕТ: Назви компаній (Хлібокомбінат, М'ясокомбінат, Молокозавод).
3. ВІДКИДАЙ: Алкоголь, IT, Будівництво, Банки, Логістику (якщо немає продажів).
4. Якщо інформації в картці замало для висновку про скоропорт - ПРОПУСКАЙ кандидата.

ФОРМАТ ВІДПОВІДІ:
✅ [Назва посади з резюме] - [Коротко чому підходить згідно з текстом] - [Посилання]
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати для фільтрації:\n{candidate_batch}"}]}],
            "generationConfig": {"temperature": 0.0} # МАКСИМАЛЬНА ТОЧНІСТЬ
        }
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        if 'candidates' in res:
            text = res['candidates'][0]['content']['parts'][0]['text']
            return text if "✅" in text else None
    except: return None
    return None

def get_work_ua_data():
    processed = get_processed_links()
    all_candidates = []
    new_links_to_save = []
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    
    for loc in LOCATIONS:
        for q in QUERIES:
            url = f"https://www.work.ua/resumes-{loc}-{urllib.parse.quote(q)}/?days=122"
            try:
                r = requests.get(url, headers=headers, timeout=20)
                soup = BeautifulSoup(r.text, 'html.parser')
                cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
                
                for card in cards:
                    link_tag = card.find('a', href=True)
                    if link_tag:
                        link = "https://www.work.ua" + link_tag['href'].split('?')[0]
                        if link not in processed:
                            title = link_tag.get_text(strip=True)
                            # ЗБИРАЄМО БІЛЬШЕ ТЕКСТУ З КАРТКИ ДЛЯ ШІ
                            info_tags = card.find_all(['p', 'span', 'ul'], class_=['text-muted', 'mt-xs'])
                            full_info = " ".join([t.get_text(strip=True) for t in info_tags])
                            
                            all_candidates.append(f"ПОСАДА: {title}\nДОСВІД: {full_info}\nПОСИЛАННЯ: {link}")
                            new_links_to_save.append(link)
                            processed.add(link)
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
        batch_size = 15
        for i in range(0, len(candidates), batch_size):
            batch = "\n\n".join(candidates[i:i+batch_size])
            report = get_ai_analysis(batch)
            if report:
                send_telegram(f"👔 **Топ-кандидати (Комерція/Скоропорт):**\n\n{report}")
            time.sleep(2)
        save_processed_links(links)

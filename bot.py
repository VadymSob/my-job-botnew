import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. НАЛАШТУВАННЯ ПОШУКУ ---
# Тільки Комерційний директор, щоб не забивати звіт лінійним персоналом
QUERIES = ["комерційний директор", "commercial director"]
LOCATIONS = ["ukraine", "vinnytsya"]
DB_FILE = "processed_resumes.txt"

# --- 2. ДІАГНОСТИЧНИЙ ПРОМПТ (ТЕСТОВИЙ РЕЖИМ) ---
AI_CRITERIA = """
Ти - рекрутер хлібозаводу. Ми тестуємо точність фільтрації.
Шукаємо: Комерційний директор (Досвід: хліб, м'ясо, молоко, кондитерка - СКОРОПОРТ).

ТВОЄ ЗАВДАННЯ: 
Проаналізуй кожного кандидата зі списку і дай відповідь СУВОРО за таким форматом:
- Якщо підходить: ✅ [Назва посади] - [Чому підходить (напр. 8 років на хлібзаводі)] - [Посилання]
- Якщо НЕ підходить: ❌ [Назва посади] - [Причина відмови (напр. досвід тільки в IT або алкоголі)] - [Посилання]

Важливо: Не вигадуй імен! Використовуй тільки наданий текст.
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
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nСписок кандидатів:\n{candidate_batch}"}]}],
            "generationConfig": {"temperature": 0.0} # Без фантазій
        }
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        if 'candidates' in res:
            return res['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        return f"⚠️ Помилка ШІ: {str(e)}"
    return None

def get_work_ua_data():
    processed = get_processed_links()
    all_candidates = []
    new_links_to_save = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    
    for loc in LOCATIONS:
        for q in QUERIES:
            # Дивимось перші 2 сторінки для кожного запиту
            for page in range(1, 3):
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
                                title = link_tag.get_text(strip=True)
                                # Збираємо опис досвіду з картки
                                info_tags = card.find_all(['p', 'span', 'li'], class_=['text-muted', 'mt-xs'])
                                info_text = " ".join([t.get_text(strip=True) for t in info_tags])
                                
                                all_candidates.append(f"ПОСАДА: {title}\nОПИС: {info_text}\nПОСИЛАННЯ: {link}")
                                new_links_to_save.append(link)
                                processed.add(link)
                    time.sleep(1)
                except: continue
    return all_candidates, new_links_to_save

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id or not message.strip(): return
    
    # Розбиваємо повідомлення, якщо воно занадто довге для Telegram
    if len(message) > 4000:
        for x in range(0, len(message), 4000):
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                          data={"chat_id": chat_id, "text": message[x:x+4000], "disable_web_page_preview": True})
    else:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True})

if __name__ == "__main__":
    print("Запуск діагностики кандидатів...")
    candidates, links = get_work_ua_data()
    
    if candidates:
        print(f"Знайдено нових: {len(candidates)}. Аналізую...")
        # Обробляємо по 10 кандидатів за запит
        batch_size = 10
        for i in range(0, len(candidates), batch_size):
            batch = "\n\n".join(candidates[i:i+batch_size])
            report = get_ai_analysis(batch)
            if report:
                send_telegram(f"🔍 **Діагностика кандидатів (Група {i//batch_size + 1}):**\n\n{report}")
            time.sleep(2)
        
        save_processed_links(links)
        print("Готово. Перевірте Telegram.")
    else:
        print("Нових кандидатів не знайдено.")

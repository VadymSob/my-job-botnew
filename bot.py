import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. НАЛАШТУВАННЯ ПОШУКУ ---
QUERIES = ["комерційний директор", "commercial director"]
LOCATIONS = ["ukraine", "vinnytsya"]
DB_FILE = "processed_resumes.txt"

# --- 2. СУВОРИЙ ТРИРІВНЕВИЙ ФІЛЬТР (АНТИ-ГАЛЮЦИНАЦІЯ) ---
AI_CRITERIA = """
Ти - професійний рекрутер. Твоє завдання - класифікувати кандидатів за рівнем відповідності.
Шукаємо: Комерційний директор для харчового підприємства.

КЛАСИФІКАЦІЯ (використовуй тільки ці категорії):

1. ⭐ СУПЕР ПРІОРИТЕТ:
- Посада: Комерційний директор / Директор з продажів (CCO).
- Сфера: СКОРОПОРТ (М'ясокомбінати, Хлібзаводи, Молокозаводи).
- Обов'язково вкажи назву заводу/компанії з тексту.

2. ✅ ПРІОРИТЕТ:
- Посада: Комерційний директор / ТОП-менеджер.
- Сфера: Будь-яка інша ХАРЧОВА продукція (Кондитерка, Напої, FMCG Food).

3. ❌ ВІДМОВА:
- Немає досвіду топ-менеджера саме в харчовій сфері.
- Сфери: Авто (шини/запчастини), IT, Будівництво, Фармація, Логістика - ОДРАЗУ ВІДМОВА.

СУВОРІ ПРАВИЛА:
- Заборонено вигадувати досвід. Якщо в тексті немає слова "хліб", "м'ясо" або назви заводу - не пиши про них.
- Якщо бачиш "Шини", "Запчастини", "IT" - це автоматично ❌.
- Формат відповіді: [Категорія] - [Посада] - [Компанія/Сфера] - [Посилання]
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
    # ОНОВЛЕНО: Використовуємо стабільну версію v1 замість v1beta
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    payload = {
        "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nСписок кандидатів:\n{batch_text}"}]}],
        "generationConfig": {
            "temperature": 0.0,  # Максимальна точність, 0 - без фантазій
            "topP": 0.95,
            "topK": 40
        }
    }
    
    try:
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        if 'candidates' in res and len(res['candidates']) > 0:
            return res['candidates'][0]['content']['parts'][0]['text']
        else:
            error_msg = res.get('error', {}).get('message', 'Невідома помилка API')
            print(f"DEBUG: ШІ не дав відповіді. Причина: {error_msg}")
            return None
    except Exception as e:
        print(f"DEBUG: Помилка запиту до ШІ: {e}")
        return None

def get_work_ua_data():
    processed = get_processed_links()
    all_candidates = []
    new_links = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
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
                            # Збираємо весь текст картки для кращого аналізу
                            full_card_text = card.get_text(" ", strip=True)
                            all_candidates.append(f"ДАНІ: {full_card_text}\nПосилання: {link}")
                            new_links.append(link)
                            processed.add(link)
                time.sleep(1)
            except Exception as e:
                print(f"Помилка при зборі даних з Work.ua: {e}")
                continue
    return all_candidates, new_links

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id or not message.strip(): return
    
    # Розбиваємо довгі повідомлення (ліміт TG 4096 символів)
    if len(message) > 4000:
        for x in range(0, len(message), 4000):
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                          data={"chat_id": chat_id, "text": message[x:x+4000], "disable_web_page_preview": True})
    else:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      data={"chat_id": chat_id, "text": message, "disable_web_page_preview": True})

if __name__ == "__main__":
    print("Запуск бота: пошук нових резюме...")
    candidates, links = get_work_ua_data()
    
    if candidates:
        print(f"Знайдено {len(candidates)} нових кандидатів. Починаю аналіз...")
        
        # Обробляємо по 5 осіб, щоб вписатися в ліміти безкоштовного API
        batch_size = 5
        for i in range(0, len(candidates), batch_size):
            batch = "\n---\n".join(candidates[i:i+batch_size])
            report = get_ai_analysis(batch)
            
            if report:
                send_telegram(f"🔍 **Звіт по кандидатах (Група {i//batch_size + 1}):**\n\n{report}")
                print(f"Група {i//batch_size + 1} успішно оброблена та надіслана.")
            
            # Велика пауза 25 секунд, щоб уникнути помилки 429 (Resource Exhausted)
            time.sleep(25)
            
        save_processed_links(links)
        print("Всі нові кандидати оброблені.")
    else:
        print("Нових кандидатів за вашим запитом не знайдено.")

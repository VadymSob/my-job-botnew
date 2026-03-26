import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. НАЛАШТУВАННЯ ПОШУКУ ---
QUERIES = ["комерційний директор", "commercial director"]
LOCATIONS = ["ukraine", "vinnytsya"]
DB_FILE = "processed_resumes.txt"

# --- 2. СУВОРИЙ ТРИРІВНЕВИЙ ФІЛЬТР ---
AI_CRITERIA = """
Ти - професійний рекрутер. Класифікуй кандидатів.
Шукаємо: Комерційний директор для харчового підприємства.

КЛАСИФІКАЦІЯ:
1. ⭐ СУПЕР ПРІОРИТЕТ: Комерційний директор + СКОРОПОРТ (М'ясо, Хліб, Молоко).
2. ✅ ПРІОРИТЕТ: Комерційний директор + будь-яка інша ХАРЧОВА продукція (Кондитерка, Напої).
3. ❌ ВІДМОВА: Немає досвіду ТОП-менеджера в харчовій сфері (Шини, IT, Будівництво - ВІДМОВА).

СУВОРІ ПРАВИЛА:
- Заборонено вигадувати досвід. Немає харчового досвіду в тексті = ❌.
- Формат: [Категорія] - [Посада] - [Компанія/Сфера] - [Посилання]
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
    try:
        # 1. Запитуємо у Google список доступних ВАМ моделей
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        models_res = requests.get(list_url, timeout=30).json()
        
        # Знаходимо першу доступну модель, що вміє генерувати контент (flash або pro)
        active_model = next((m['name'] for m in models_res.get('models', []) 
                            if 'generateContent' in m['supportedGenerationMethods']), None)
        
        if not active_model:
            print("DEBUG: Не знайдено жодної доступної моделі в вашому API.")
            return None

        # 2. Надсилаємо запит саме цій моделі
        url = f"https://generativelanguage.googleapis.com/v1beta/{active_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nСписок:\n{batch_text}"}]}],
            "generationConfig": {"temperature": 0.0}
        }
        
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        if 'candidates' in res and len(res['candidates']) > 0:
            return res['candidates'][0]['content']['parts'][0]['text']
        else:
            print(f"DEBUG: Помилка генерації ({active_model}): {res}")
            return None
    except Exception as e:
        print(f"DEBUG: Помилка запиту: {e}")
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
                            full_card_text = card.get_text(" ", strip=True)
                            all_candidates.append(f"ДАНІ: {full_card_text}\nПосилання: {link}")
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
    print("Запуск бота: пошук нових резюме...")
    candidates, links = get_work_ua_data()
    
    if candidates:
        print(f"Знайдено {len(candidates)}. Аналізую...")
        # Обробляємо по 5 осіб для стабільності
        batch_size = 5
        for i in range(0, len(candidates), batch_size):
            batch = "\n---\n".join(candidates[i:i+batch_size])
            report = get_ai_analysis(batch)
            if report:
                send_telegram(f"🔍 **Звіт (Група {i//batch_size + 1}):**\n\n{report}")
                print(f"Група {i//batch_size + 1} готова.")
            time.sleep(25)
        save_processed_links(links)
    else:
        print("Нових кандидатів не знайдено.")

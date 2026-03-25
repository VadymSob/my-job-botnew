import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. КРИТЕРІЇ ВІДБОРУ ДЛЯ ШІ ---
AI_CRITERIA = """
Ти - професійний рекрутер хлібозаводу (Вінницька обл.). Шукаємо Керівника продажу або Комерційного директора.
Специфіка: FMCG (хліб, продукти харчування). 

ЗАВДАННЯ: 
1. Проаналізуй список резюме. 
2. Відсій тих, хто НЕ працював з продуктами харчування (FMCG Food) або НЕ має досвіду управління командою.
3. ВІДПОВІДАЙ СУВОРО за шаблоном для кожного підходящого:
✅ [ПІБ/Посада] - [Коротко: чому підходить] - [Посилання]

Якщо підходящих немає, напиши: "Нових релевантних кандидатів за 15 днів не знайдено."
Не пиши вступних фраз. Тільки список.
"""

DB_FILE = "processed_resumes.txt"

def get_processed_links():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_links(links):
    if not links: return
    with open(DB_FILE, "a") as f:
        for link in links:
            f.write(link + "\n")

def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key: return "⚠️ Помилка: Немає API ключа."
    
    try:
        # Автопідбір доступної моделі
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_res = requests.get(list_url, timeout=30).json()
        target_model = next((m['name'] for m in list_res.get('models', []) if 'generateContent' in m['supportedGenerationMethods']), None)
        
        if not target_model: return "❌ Робочу модель не знайдено."

        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати для аналізу:\n{candidate_data}"}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2000}
        }
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        return res['candidates'][0]['content']['parts'][0]['text'] if 'candidates' in res else "⚠️ Помилка аналізу ШІ."
    except Exception as e:
        return f"❌ Помилка зв'язку з ШІ: {str(e)}"

def get_work_ua_resumes():
    # Розширений список запитів
    queries = [
        "комерційний директор", 
        "керівник відділу продажу", 
        "директор з продажу", 
        "регіональний менеджер", 
        "директор філії"
    ]
    
    processed = get_processed_links()
    combined_data = ""
    new_links = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Cookie": os.getenv("WORK_UA_COOKIE", "")
    }
    
    for q in queries:
        encoded_q = urllib.parse.quote(q)
        # ?days=122 — фільтр на Work.ua "за останні 14-15 днів"
        url = f"https://www.work.ua/resumes-vinnytsya-{encoded_q}/?days=122"
        
        try:
            r = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
            
            for card in cards:
                link_tag = card.find('a', href=True)
                if link_tag:
                    # Очищуємо посилання від зайвих параметрів
                    link = "https://www.work.ua" + link_tag['href'].split('?')[0]
                    
                    if link not in processed:
                        name = link_tag.get_text(strip=True)
                        info = card.find('p', class_='text-muted')
                        combined_data += f"КАНДИДАТ: {name}\nІНФО: {info.get_text(strip=True) if info else ''}\nПОСИЛАННЯ: {link}\n\n"
                        new_links.append(link)
                        processed.add(link) # Щоб не дублювати в межах одного запуску
            time.sleep(1) # Невелика пауза між запитами
        except:
            continue
            
    return combined_data, new_links

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id: return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": message[:4000], 
        "disable_web_page_preview": True
    }
    requests.post(url, data=payload)

if __name__ == "__main__":
    print("Збираю нові резюме...")
    raw_data, links_to_save = get_work_ua_resumes()
    
    if raw_data:
        print(f"Знайдено нових: {len(links_to_save)}. Аналізую...")
        report = get_ai_analysis(raw_data)
        
        # Відправляємо в ТГ тільки якщо ШІ когось обрав
        if "не знайдено" not in report.lower():
            send_telegram(f"🤖 **Звіт ШІ-рекрутера (Нові за 15 днів):**\n\n{report}")
        else:
            print("ШІ відсіяв усіх кандидатів як нерелевантних.")
            
        # Зберігаємо ВСІ побачені посилання, щоб завтра їх не чіпати
        save_processed_links(links_to_save)
    else:
        print("Нічого нового за 15 днів не знайдено.")

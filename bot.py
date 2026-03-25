import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. КРИТЕРІЇ ВІДБОРУ (ОНОВЛЕНО: БІЛЬШ ГНУЧКІ) ---
AI_CRITERIA = """
Ти - досвідчений HR-директор. Шукаємо Керівника продажу / Комерційного директора для хлібозаводу (Вінниця).
Сфера: FMCG (товари повсякденного попиту).

ТВОЄ ЗАВДАННЯ:
1. Проаналізуй список резюме.
2. ПРІОРИТЕТ: Кандидати з досвідом у продуктах харчування (хліб, молоко, м'ясо, кондитерка).
3. ТАКОЖ РОЗГЛЯДАЙ: Сильних управлінців з будь-якого FMCG (напої, побутова хімія, косметика) або системного ритейлу.
4. ОБОВ'ЯЗКОВО: Досвід керування відділом продажів або філією.

ФОРМАТ ВІДПОВІДІ (Тільки список):
✅ [ПІБ/Посада] - [Чому підходить (наприклад: досвід у молочній сфері 5 років)] - [Посилання]

Якщо зовсім немає релевантних (наприклад, тільки ІТ або будівництво), напиши: "Нових релевантних кандидатів не знайдено."
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
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_res = requests.get(list_url, timeout=30).json()
        target_model = next((m['name'] for m in list_res.get('models', []) if 'generateContent' in m['supportedGenerationMethods']), None)
        
        if not target_model: return "❌ Робочу модель не знайдено."

        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати для аналізу:\n{candidate_data}"}]}],
            "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2000}
        }
        r = requests.post(url, json=payload, timeout=60)
        res = r.json()
        return res['candidates'][0]['content']['parts'][0]['text'] if 'candidates' in res else "⚠️ Помилка аналізу ШІ."
    except Exception as e:
        return f"❌ Помилка зв'язку з ШІ: {str(e)}"

def get_work_ua_resumes():
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
        url = f"https://www.work.ua/resumes-vinnytsya-{encoded_q}/?days=122"
        
        try:
            r = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
            
            for card in cards:
                link_tag = card.find('a', href=True)
                if link_tag:
                    link = "https://www.work.ua" + link_tag['href'].split('?')[0]
                    if link not in processed:
                        name = link_tag.get_text(strip=True)
                        info = card.find('p', class_='text-muted')
                        combined_data += f"КАНДИДАТ: {name}\nІНФО: {info.get_text(strip=True) if info else ''}\nПОСИЛАННЯ: {link}\n\n"
                        new_links.append(link)
                        processed.add(link)
            time.sleep(1)
        except:
            continue
            
    return combined_data, new_links

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message[:4000], "disable_web_page_preview": True})

if __name__ == "__main__":
    raw_data, links_to_save = get_work_ua_resumes()
    
    if raw_data:
        report = get_ai_analysis(raw_data)
        
        # Надсилаємо звіт у ТГ
        send_telegram(f"🤖 **Звіт ШІ-рекрутера (Аналіз {len(links_to_save)} нових):**\n\n{report}")
        
        # Зберігаємо посилання
        save_processed_links(links_to_save)
    else:
        print("Нічого нового за 15 днів не знайдено.")

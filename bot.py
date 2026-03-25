import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import time

# --- 1. ПАРАМЕТРИ ПОШУКУ ---
QUERIES = ["комерційний директор", "директор хлібзаводу", "керівник відділу продажу", "директор з продажу"]
LOCATIONS = ["ukraine", "vinnytsya"] # Україна в пріоритеті для релокації
MAX_PAGES = 3 # Скільки сторінок результатів проходити за кожним запитом
DB_FILE = "processed_resumes.txt"

AI_CRITERIA = """
Ти - рекрутер хлібозаводу. Шукаємо ТОП-менеджера.
ПРАВИЛА:
1. ПРІОРИТЕТ: Досвід на ХЛІБОЗАВОДАХ, хлібокомбінатах, КХП (це ідеальні кандидати).
2. СУМІЖНІ: М'ясокомбінати, молочна продукція, FMCG (швидкопсувні товари).
3. НЕ ВІДКИДАЙ за місто проживання, якщо вказано "готовий до переїзду".
4. ФОРМАТ: ✅ [ПІБ/Посада] - [Чому підходить] - [Посилання]
"""

def get_processed_links():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_links(links):
    if not links: return
    with open(DB_FILE, "a") as f:
        for link in links: f.write(link + "\n")

def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_res = requests.get(list_url, timeout=30).json()
        target_model = next((m['name'] for m in list_res.get('models', []) if 'generateContent' in m['supportedGenerationMethods']), None)
        
        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати:\n{candidate_data}"}]}],
            "generationConfig": {"temperature": 0.1}
        }
        r = requests.post(url, json=payload, timeout=60)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except: return "⚠️ Помилка аналізу ШІ."

def get_work_ua_data():
    processed = get_processed_links()
    combined_data = ""
    new_links = []
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    
    for loc in LOCATIONS:
        for q in QUERIES:
            for page in range(1, MAX_PAGES + 1):
                encoded_q = urllib.parse.quote(q)
                # ?days=122 (15 днів), &page=X (глибина)
                url = f"https://www.work.ua/resumes-{loc}-{encoded_q}/?days=122&page={page}"
                try:
                    r = requests.get(url, headers=headers, timeout=20)
                    if r.status_code != 200: break
                    
                    soup = BeautifulSoup(r.text, 'html.parser')
                    cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
                    
                    if not cards: break # Якщо сторінка порожня, йдемо до наступного запиту
                    
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
                except: continue
                
    return combined_data, new_links

if __name__ == "__main__":
    print("Глибокий пошук за 15 днів по всій Україні...")
    raw_data, links_to_save = get_work_ua_data()
    
    if raw_data:
        print(f"Знайдено нових карток: {len(links_to_save)}. Аналізую...")
        report = get_ai_analysis(raw_data)
        
        token = os.getenv("TELEGRAM_TOKEN")
        chat_id = os.getenv("CHAT_ID")
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      data={"chat_id": chat_id, "text": f"🤖 **Звіт ШІ (Глибокий пошук):**\n\n{report}", "disable_web_page_preview": True})
        
        save_processed_links(links_to_save)
    else:
        print("Нічого нового.")

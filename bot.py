import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

# --- 1. КРИТЕРІЇ ВІДБОРУ ---
AI_CRITERIA = """
Ти - рекрутер хлібозаводу (Вінниця). Шукаємо Керівника продажу/Комерційного директора.
Специфіка: FMCG (хліб, продукти). 
ЗАВДАННЯ: Відсій тих, хто НЕ з продуктів або без досвіду управління.
Напиши: ✅ [ПІБ] - [Чому підходить] - [Посилання]
Якщо нових релевантних немає, напиши: "Нових релевантних кандидатів за 15 днів не знайдено."
"""

DB_FILE = "processed_resumes.txt"

def get_processed_links():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return set(line.strip() for line in f if line.strip())
    return set()

def save_processed_links(links):
    with open(DB_FILE, "a") as f:
        for link in links:
            f.write(link + "\n")

def get_ai_analysis(candidate_data):
    api_key = os.getenv("GEMINI_API_KEY")
    try:
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        list_res = requests.get(list_url, timeout=30).json()
        target_model = next((m['name'] for m in list_res.get('models', []) if 'generateContent' in m['supportedGenerationMethods']), None)
        
        url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={api_key}"
        payload = {"contents": [{"parts": [{"text": f"{AI_CRITERIA}\n\nКандидати:\n{candidate_data}"}]}]}
        r = requests.post(url, json=payload, timeout=60)
        return r.json()['candidates'][0]['content']['parts'][0]['text']
    except: return "⚠️ Помилка аналізу ШІ."

def get_work_ua_resumes():
    # Розширений список запитів
    queries = ["комерційний директор", "керівник відділу продажу", "директор з продажу", "регіональний менеджер", "директор філії"]
    processed = get_processed_links()
    new_candidates_data = ""
    current_batch_links = []
    
    headers = {"User-Agent": "Mozilla/5.0", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    
    for q in queries:
        encoded_q = urllib.parse.quote(q)
        # Параметр ?days=122 (на Work.ua це фільтр "за останні 14-15 днів")
        url = f"https://www.work.ua/resumes-vinnytsya-{encoded_q}/?days=122"
        try:
            r = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, 'html.parser')
            cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
            
            for card in cards:
                link_tag = card.find('a', href=True)
                if link_tag:
                    link = "https://www.work.ua" + link_tag['href'].split('?')[0] # чисте посилання
                    if link not in processed:
                        name = link_tag.get_text(strip=True)
                        info = card.find('p', class_='text-muted')
                        new_candidates_data += f"КАНДИДАТ: {name}\nІНФО: {info.get_text(strip=True) if info else ''}\nПОСИЛАННЯ: {link}\n\n"
                        current_batch_links.append(link)
        except: continue
        
    return new_candidates_data, current_batch_links

if __name__ == "__main__":
    raw_candidates, links_to_save = get_work_ua_resumes()
    
    if raw_candidates:
        report = get_ai_analysis(raw_candidates)
        # Надсилаємо в ТГ тільки якщо ШІ когось обрав (не видав фразу "не знайдено")
        if "не знайдено" not in report.lower():
            token = os.getenv("TELEGRAM_TOKEN")
            chat_id = os.getenv("CHAT_ID")
            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                          data={"chat_id": chat_id, "text": f"🤖 **Звіт ШІ-рекрутера (Нові за 15 днів):**\n\n{report}", "disable_web_page_preview": True})
        
        # Зберігаємо посилання, щоб не аналізувати їх завтра
        save_processed_links(links_to_save)
    else:
        print("Нічого нового за 15 днів.")

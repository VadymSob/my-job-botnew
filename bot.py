import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

def get_candidates():
    # Посилання саме на розділ РЕЗЮМЕ
    base_url = "https://www.work.ua/resumes-vinnytsya-"
    query = urllib.parse.quote("комерційний директор")
    url = f"{base_url}{query}/"
    
    print(f"DEBUG: URL: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie": os.getenv("WORK_UA_COOKIE", "")
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        print(f"DEBUG: Status: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Шукаємо всі можливі варіанти карток (Work.ua часто їх змінює)
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        if not cards:
            cards = soup.select('div.card.card-hover') # Альтернативний селектор
            
        print(f"DEBUG: Found cards: {len(cards)}")

        if not cards:
            return "📭 На жаль, сьогодні нових кандидатів не знайдено. Перевірте актуальність Cookie у GitHub Secrets."

        report = "💼 *Нові кандидати (Вінниця):*\n\n"
        count = 0
        for card in cards:
            if count >= 5: break # Обмежуємо першими п'ятьма
            
            # Шукаємо заголовок (ПІБ або Посада)
            link_tag = card.find('a', href=True)
            if link_tag and '/resumes/' in link_tag['href']:
                name = link_tag.get_text(strip=True)
                full_link = "https://www.work.ua" + link_tag['href']
                
                # Шукаємо опис
                desc_tag = card.find('p', class_='text-muted') or card.find('div', class_='mt-xs')
                desc = desc_tag.get_text(strip=True)[:100] + "..." if desc_tag else "Досвід не вказано"
                
                report += f"👤 *{name}*\n📝 {desc}\n🔗 [Переглянути резюме]({full_link})\n\n"
                count += 1
        
        return report

    except Exception as e:
        return f"❌ Помилка скрипта: {str(e)}"

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    # Використовуємо спрощений Markdown, щоб уникнути помилки 400
    data = {
        "chat_id": chat_id, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    r = requests.post(url, data=data)
    print(f"DEBUG: Telegram Response: {r.status_code} {r.text}")

if __name__ == "__main__":
    content = get_candidates()
    send_telegram(content)

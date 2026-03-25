import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

def get_candidates():
    # Правильне кодування кирилиці для посилання
    base_url = "https://www.work.ua/resumes-vinnytsya-"
    query = urllib.parse.quote("комерційний+директор")
    url = f"{base_url}{query}/"
    
    print(f"DEBUG: Connecting to {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Cookie": os.getenv("WORK_UA_COOKIE", "")
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f"DEBUG: Status Code: {response.status_code}")
        
        if response.status_code != 200:
            return f"❌ Помилка: Сайт повернув статус {response.status_code}"

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Оновлений пошук: шукаємо всі картки резюме
        cards = soup.find_all('div', class_='card-resumes')
        if not cards:
            # Спробуємо альтернативний пошук, якщо структура трохи інша
            cards = soup.select('.card.card-hover.resume-link')
            
        print(f"DEBUG: Found {len(cards)} cards")

        if not cards:
            return "📭 Кандидатів за запитом не знайдено. Перевірте Cookie або посилання."

        report = "💼 **Нові кандидати (Work.ua):**\n\n"
        for card in cards[:5]:  # Беремо перші 5
            title_tag = card.find('h2') or card.find('a')
            if title_tag:
                name = title_tag.get_text(strip=True)
                link = "https://www.work.ua" + title_tag.find('a')['href'] if title_tag.find('a') else "No link"
                
                # Спробуємо дістати досвід/вік
                info = card.find('p', class_='text-muted')
                info_text = info.get_text(strip=True) if info else ""
                
                report += f"👤 {name}\nℹ️ {info_text}\n🔗 {link}\n\n"
        
        return report

    except Exception as e:
        print(f"DEBUG: Error occurred: {e}")
        return f"❌ Сталася помилка при роботі скрипта: {e}"

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id:
        print("DEBUG: Telegram Token or Chat ID is missing!")
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})
    print(f"DEBUG: Telegram response: {r.status_code}")

if __name__ == "__main__":
    content = get_candidates()
    print("DEBUG: Report prepared. Sending...")
    send_telegram(content)

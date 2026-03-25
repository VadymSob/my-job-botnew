import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

def get_work_ua():
    # Пошук комерційних директорів у Вінниці
    base_url = "https://www.work.ua/resumes-vinnytsya-"
    query = urllib.parse.quote("комерційний директор")
    url = f"{base_url}{query}/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Cookie": os.getenv("WORK_UA_COOKIE", "")
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        
        if not cards:
            return "📭 На Work.ua поки немає нових кандидатів за вашим запитом."

        report = "🏙 **Свіжі кандидати з Work.ua (Вінниця):**\n\n"
        
        for card in cards[:5]: # Беремо топ-5 найкращих результатів
            link_tag = card.find('a', href=True)
            if link_tag and '/resumes/' in link_tag['href']:
                name = link_tag.get_text(strip=True)
                full_link = "https://www.work.ua" + link_tag['href']
                
                # Додаємо опис (вік, досвід), якщо він є
                info_tag = card.find('p', class_='text-muted')
                info_text = info_tag.get_text(strip=True) if info_tag else "Досвід вказано в резюме"
                
                report += f"👤 *{name}*\n📝 {info_text}\n🔗 [Відкрити резюме]({full_link})\n\n"
        
        return report
    except Exception as e:
        return f"❌ Помилка з'єднання з Work.ua: {str(e)}"

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id: return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": message, 
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, data=payload)

if __name__ == "__main__":
    content = get_work_ua()
    send_telegram(content)

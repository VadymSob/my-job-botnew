import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

def get_work_ua():
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
        
        report = "🏙 **Work.ua (Вінниця):**\n"
        if not cards:
            return report + "📭 Кандидатів не знайдено.\n\n"
        
        count = 0
        for card in cards:
            if count >= 3: break
            link_tag = card.find('a', href=True)
            if link_tag and '/resumes/' in link_tag['href']:
                name = link_tag.get_text(strip=True)
                full_link = "https://www.work.ua" + link_tag['href']
                report += f"👤 {name}\n🔗 {full_link}\n\n"
                count += 1
        return report
    except:
        return "❌ Помилка Work.ua\n\n"

def get_robota_ua():
    url = "https://robota.ua/candidates/komertsiynyy-dyrektor/vinnytsia?inside=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Cookie": os.getenv("ROBOTA_UA_COOKIE", "")
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Пошук карток на Robota.ua
        cards = soup.find_all('alliance-candidate-card')
        if not cards:
            cards = soup.select('div.cv-card') or soup.select('.santa-m-0')

        report = "🚀 **Robota.ua (Вінниця):**\n"
        if not cards:
            return report + "⚠️ Дані не зчитано (оновіть Cookie).\n\n"
        
        count = 0
        for card in cards:
            if count >= 3: break
            link_tag = card.find('a', href=True)
            name_tag = card.find('h3') or card.find('p', class_='santa-typo-h3') or link_tag
            
            if link_tag and name_tag:
                name_text = name_tag.get_text(strip=True)
                path = link_tag['href']
                full_link = f"https://robota.ua{path}" if path.startswith('/') else path
                report += f"👤 {name_text}\n🔗 {full_link}\n\n"
                count += 1
        return report
    except:
        return "❌ Помилка Robota.ua\n\n"

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
    final_report = "📅 **Щоденний звіт по кандидатах**\n\n"
    final_report += get_work_ua()
    final_report += "--------------------------\n"
    final_report += get_robota_ua()
    send_telegram(final_report)

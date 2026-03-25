import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

def get_work_ua():
    url = "https://www.work.ua/resumes-vinnytsya-" + urllib.parse.quote("комерційний директор") + "/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Cookie": os.getenv("WORK_UA_COOKIE", "")
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        
        report = "🏙 **Work.ua (Вінниця):**\n"
        if not cards: return report + "Нікого не знайдено\n\n"
        
        for card in cards[:3]:
            link_tag = card.find('a', href=True)
            if link_tag and '/resumes/' in link_tag['href']:
                name = link_tag.get_text(strip=True)
                report += f"👤 {name}\n🔗 https://www.work.ua{link_tag['href']}\n\n"
        return report
    except: return "❌ Помилка Work.ua\n\n"

def get_robota_ua():
    url = "https://robota.ua/candidates/komertsiynyy-dyrektor/vinnytsya?inside=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Cookie": os.getenv("ROBOTA_UA_COOKIE", "")
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # На Robota.ua картки зазвичай мають класи пов'язані з cv-card або подібні
        cards = soup.select('alliance-candidate-card') or soup.select('.cv-card')
        
        report = "🚀 **Robota.ua (Вінниця):**\n"
        if not cards: return report + "Нікого не знайдено (перевірте Cookie)\n\n"
        
        for card in cards[:3]:
            link_tag = card.find('a', href=True)
            name = card.find('h3') or link_tag
            if name:
                name_text = name.get_text(strip=True)
                link = "https://robota.ua" + link_tag['href'] if link_tag['href'].startswith('/') else link_tag['href']
                report += f"👤 {name_text}\n🔗 {link}\n\n"
        return report
    except: return "❌ Помилка Robota.ua\n\n"

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

if __name__ == "__main__":
    final_report = "📅 **Щоденний звіт по кандидатах**\n\n"
    final_report += get_work_ua()
    final_report += "--------------------------\n"
    final_report += get_robota_ua()
    send_telegram(final_report)

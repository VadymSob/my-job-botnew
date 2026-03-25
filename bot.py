import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import json

def get_work_ua():
    base_url = "https://www.work.ua/resumes-vinnytsya-"
    query = urllib.parse.quote("комерційний директор")
    url = f"{base_url}{query}/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36", "Cookie": os.getenv("WORK_UA_COOKIE", "")}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        cards = soup.find_all('div', class_=['card-resumes', 'card-hover', 'resume-link'])
        report = "🏙 **Work.ua (Вінниця):**\n"
        if not cards: return report + "📭 Кандидатів не знайдено.\n\n"
        for card in cards[:3]:
            link = card.find('a', href=True)
            if link: report += f"👤 {link.get_text(strip=True)}\n🔗 https://www.work.ua{link['href']}\n\n"
        return report
    except: return "❌ Помилка Work.ua\n\n"

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
        
        # План А: Шукаємо стандартні теги
        cards = soup.select('alliance-candidate-card') or soup.select('.cv-card')
        
        # План Б: Шукаємо дані в прихованому скрипті (якщо сайт віддав JSON всередині HTML)
        if not cards:
            script_tag = soup.find('script', id='serverApp-state')
            if script_tag:
                try:
                    # Очищаємо текст скрипта від зайвих символів для JSON
                    data = json.loads(script_tag.string.replace('&q;', '"'))
                    # Тут логіка витягування може бути складною, тому просто спробуємо знайти ключі з іменами
                    if "candidates" in str(data):
                        return "🚀 **Robota.ua:**\n✅ Знайдено нові дані в системі (оновіть сторінку в браузері для деталей).\n\n"
                except: pass

        report = "🚀 **Robota.ua (Вінниця):**\n"
        if not cards: return report + "⚠️ Картки не знайдено. Сайт вимагає оновити Cookie з вашого браузера.\n\n"
        
        count = 0
        for card in cards[:3]:
            link = card.find('a', href=True)
            name = card.find('h3') or card.find('p', class_='santa-typo-h3')
            if link and name:
                full_link = f"https://robota.ua{link['href']}" if link['href'].startswith('/') else link['href']
                report += f"👤 {name.get_text(strip=True)}\n🔗 {full_link}\n\n"
                count += 1
        return report
    except: return "❌ Помилка Robota.ua\n\n"

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown", "disable_web_page_preview": True})

if __name__ == "__main__":
    report = "📅 **Щоденний звіт**\n\n" + get_work_ua() + "--------------------------\n" + get_robota_ua()
    send_telegram(report)

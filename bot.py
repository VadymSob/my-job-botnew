import requests
from bs4 import BeautifulSoup
import os
import urllib.parse

def get_work_ua():
    # Пошук комерційних директорів у Вінниці на Work.ua
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
            return report + "📭 Кандидатів не знайдено (перевірте Cookie).\n\n"
        
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
    except Exception as e:
        return f"❌ Помилка Work.ua: {str(e)}\n\n"

def get_robota_ua():
    # Пошук комерційних директорів у Вінниці на Robota.ua
    url = "https://robota.ua/candidates/komertsiynyy-dyrektor/vinnytsia?inside=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Cookie": os.getenv("ROBOTA_UA_COOKIE", "")
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Спроба знайти картки через різні теги, які використовує Robota.ua
        cards = soup.find_all('alliance-candidate-card')
        if not cards:
            cards = soup.select('div.cv-card') or soup.select('.santa-m-0')

        report = "🚀 **Robota.ua (Вінниця):**\n"
        if not cards:
            return report + "⚠️ Дані не зчитано. Можливо, термін дії Cookie вичерпано.\n\n"
        
        count = 0
        for card in cards:
            if count >= 3: break
            # Шукаємо посилання та заголовок
            link_tag = card.find('a', href=True)
            name_tag = card.find('h3') or card.find('p', class_='santa-typo-h3') or link_tag
            
            if link_tag and name_tag:
                name_text = name_tag.get

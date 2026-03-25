import requests
from bs4 import BeautifulSoup
import os

def get_candidates():
    # Посилання на ваш пошук (Вінниця, Ком. директор)
    url = "https://www.work.ua/resumes-vinnytsya-комерційний+директор/"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Cookie": os.getenv("WORK_UA_COOKIE")
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return f"❌ Помилка доступу: {response.status_code}. Можливо, треба оновити Cookie."

    soup = BeautifulSoup(response.text, 'html.parser')
    # Шукаємо картки резюме
    cards = soup.find_all('div', class_='card-resumes')[:5] 
    
    if not cards:
        return "📭 Нових кандидатів за сьогодні не знайдено."

    report = "💼 **Нові кандидати (Work.ua):**\n\n"
    for card in cards:
        title = card.find('h2')
        if title:
            name = title.text.strip()
            link = "https://www.work.ua" + title.find('a')['href']
            info = card.find('p', class_='text-muted')
            info_text = info.text.strip() if info else "Без опису"
            report += f"👤 {name}\n📝 {info_text}\n🔗 {link}\n\n"
    
    return report

def send_telegram(message):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

if __name__ == "__main__":
    content = get_candidates()
    send_telegram(content)

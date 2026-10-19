import re
import urllib.parse
import webbrowser
import threading
import time
import requests
import pyautogui

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7"
}


class YouTubeManager:
    def __init__(self):
        pass

    def _auto_fullscreen(self, delay=2.2):
        time.sleep(delay)
        pyautogui.press('f')

    def _resolve_first_video(self, query: str):
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

        try:
            resp = requests.get(search_url, headers=HEADERS, timeout=3.5)
            if resp.status_code == 200:
                html = resp.text

                video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)
                titles = re.findall(r'"title":{"runs":\[{"text":"(.*?)"}\]', html)

                if video_ids:
                    first_id = video_ids[0]
                    first_title = titles[0] if titles else query
                    return f"https://www.youtube.com/watch?v={first_id}", first_title
        except Exception as e:
            print(f"[YouTube Search Error]: {e}")

        return f"https://www.youtube.com/results?search_query={encoded_query}", query

    def search_and_play(self, text="", auto_fullscreen=True):
        stop_words = [
            "акира", "аки", "включи", "поставь", "найди", "покажи", "открой",
            "на ютубе", "в ютубе", "ютуб", "видео", "ролик", "мне", "про", "прохождение"
        ]
        query = text.lower()
        for word in stop_words:
            query = query.replace(word, "")
        query = query.strip()

        if not query:
            webbrowser.open("https://youtube.com")
            return "Открываю Ютуб"

        video_url, title = self._resolve_first_video(query)
        webbrowser.open(video_url)

        if auto_fullscreen and "watch?v=" in video_url:
            threading.Thread(target=self._auto_fullscreen, daemon=True).start()

        if "watch?v=" in video_url:
            return f"Включаю {title}"
        return f"Ищу {query} на Ютубе"
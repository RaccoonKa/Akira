import os
import sys
import re
import json
import urllib.parse
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TRACKER_DOMAINS = [
    "http://rutor.info",
    "http://rutor.is",
    "http://zerutor.top"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}

GAME_STOP_WORDS = [
    "repack", "fitgirl", "xatab", "механики", "decepticon", "gog",
    "steam-rip", "rip от", "[pc]", "(pc)", "pc |", "portable",
    "русификатор", "кряк", "crack", "patch", "патч", "моды", "чит",
    "trainer", "торрент игруха", "игра", "v 1.", "v.1.", "build"
]


def _get_aliases_path() -> str:
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, "core", "utils", "movie_aliases.json")


def load_movie_aliases() -> dict:
    file_path = _get_aliases_path()
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Movie Aliases Error]: {e}")
    return {}


def _fetch_from_tracker(search_term: str, limit: int = 4, is_series: bool = False) -> list[dict]:
    encoded_q = urllib.parse.quote(search_term)

    for base_url in TRACKER_DOMAINS:
        search_url = f"{base_url}/search/0/0/0/0/{encoded_q}"
        try:
            resp = requests.get(search_url, headers=HEADERS, timeout=5.0, verify=False)
            if resp.status_code != 200 or "index" not in resp.text:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")
            index_table = soup.find("div", {"id": "index"})
            if not index_table:
                continue

            rows = index_table.find_all("tr")
            results = []

            for row in rows[1:]:
                cols = row.find_all("td")
                if len(cols) < 4:
                    continue

                links = cols[1].find_all("a")
                if len(links) < 2:
                    continue

                magnet_tag = None
                for a in links:
                    href = a.get("href", "")
                    if href.startswith("magnet:"):
                        magnet_tag = a
                        break

                if not magnet_tag:
                    continue

                title_tag = links[-1]
                raw_title = title_tag.get_text(strip=True)
                magnet_url = magnet_tag["href"]

                raw_low = raw_title.lower()
                if any(sw in raw_low for sw in GAME_STOP_WORDS):
                    continue

                size_text = cols[-2].get_text(strip=True)
                seeders_text = cols[-1].get_text(strip=True)

                seeders_match = re.search(r'\d+', seeders_text)
                seeders = int(seeders_match.group(0)) if seeders_match else 0

                if seeders < 2:
                    continue

                cleaned_title = re.sub(r'\s*\(от\s+[^)]+\)', '', raw_title)
                cleaned_title = re.sub(r'\[[^\]]*перевод[^\]]*\]', '', cleaned_title, flags=re.I)

                results.append({
                    "title": cleaned_title[:85],
                    "raw_title": raw_title,
                    "magnet": magnet_url,
                    "size": size_text,
                    "seeders": seeders,
                    "is_series": any(w in raw_title.lower() for w in ["сезон", "серии", "s0", "s1", "сериал"])
                })

            if not results:
                continue

            def rank(entry):
                score = entry["seeders"]
                t_low = entry["raw_title"].lower()
                if "1080p" in t_low or "web-dl" in t_low:
                    score += 200
                if is_series and entry["is_series"]:
                    score += 150
                return score

            results.sort(key=rank, reverse=True)
            return results[:limit]

        except Exception:
            continue

    return []


def search_torrents(query: str, limit: int = 4, is_series: bool = False) -> list[dict]:
    clean_q = re.sub(r'^(?:сериал|фильм|кино|мультфильм|аниме)\s+', '', query.lower().strip()).strip()
    if not clean_q:
        return []

    aliases = load_movie_aliases()
    for alias, replacement in aliases.items():
        pattern = r'\b' + re.escape(alias.lower()) + r'\b'
        if re.search(pattern, clean_q):
            clean_q = re.sub(pattern, replacement.lower(), clean_q).strip()
            break

    res = _fetch_from_tracker(clean_q, limit=limit, is_series=is_series)
    if res:
        return res

    if "ё" in clean_q:
        alt_q = clean_q.replace("ё", "е")
        res = _fetch_from_tracker(alt_q, limit=limit, is_series=is_series)
        if res:
            return res
    elif "е" in clean_q:
        alt_q = clean_q.replace("е", "ё")
        res = _fetch_from_tracker(alt_q, limit=limit, is_series=is_series)
        if res:
            return res

    return []
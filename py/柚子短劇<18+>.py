# -*- coding: utf-8 -*-
import sys
import re
import json
import requests
from bs4 import BeautifulSoup

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "柚子短劇"

    def init(self, extend=""):
        self.host = "https://youzidj.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
        }

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mpd|mp4|flv|mkv)(\?|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    # 1. 首頁分類與片單
    def homeContent(self, filter):
        result = {
            "class": [
                {"type_id": "/", "type_name": "首頁精選"},
                {"type_id": "/dramas/", "type_name": "全部短劇"}
            ],
            "list": []
        }

        try:
            resp = requests.get(self.host, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')

            nav_classes = []
            seen_hrefs = {"/", "/dramas/"}
            for a in soup.select('header a[href], nav a[href]'):
                href = a.get('href', '').strip()
                name = a.get_text(strip=True)
                if href.startswith('/') and href not in seen_hrefs and 1 < len(name) <= 10:
                    seen_hrefs.add(href)
                    nav_classes.append({"type_id": href, "type_name": name})
            if nav_classes:
                result["class"].extend(nav_classes[:8])

            result['list'] = self._parse_drama_cards(soup)
        except Exception:
            result['list'] = []

        return result

    def homeVideoContent(self):
        return {}

    # 2. 分類列表（支援分頁）
    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        base_path = tid if tid.startswith('http') else f"{self.host}{tid}"
        if str(pg) == "1":
            url = base_path
        else:
            sep = "&" if "?" in base_path else "?"
            url = f"{base_path}{sep}page={pg}"

        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')
            videos = self._parse_drama_cards(soup)
            result['list'] = videos
            result['page'] = int(pg)
            result['pagecount'] = 99
            result['limit'] = len(videos)
            result['total'] = 999
        except Exception:
            result['list'] = []
        return result

    # 3. 影片詳情與完整選集生成（依據 season-1-episode-N 路由規則）
    def detailContent(self, ids):
        vid = ids[0]
        url = vid if vid.startswith('http') else f"{self.host}{vid}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            html = resp.text
            soup = BeautifulSoup(html, 'lxml')

            h1 = soup.select_one('h1')
            title = h1.get_text(strip=True) if h1 else "未知短劇"

            pic = ""
            og_img = soup.select_one('meta[property="og:image"]')
            if og_img and og_img.get('content'):
                pic = og_img.get('content')
            else:
                img = soup.select_one('main img, article img, img')
                if img:
                    pic = img.get('data-src') or img.get('src') or ""
            if pic.startswith('/'):
                pic = self.host + pic

            desc = ""
            og_desc = soup.select_one('meta[name="description"], meta[property="og:description"]')
            if og_desc and og_desc.get('content'):
                desc = og_desc.get('content')

            # 取得劇集主路徑，例如 /dramas/high-school-love-story/
            parts = [p for p in vid.split('/') if p]
            drama_prefix = f"/{parts[0]}/{parts[1]}/" if len(parts) >= 2 else ""

            # 偵測目前是第幾季（預設 season-1）
            season_match = re.search(r'season-(\d+)', vid, re.I)
            season_num = season_match.group(1) if season_match else "1"

            # 尋找頁面中出現的最大集數編號
            max_ep = 0

            # 1. 從原始碼中所有 season-X-episode-Y 路徑找出最大集數
            ep_nums = re.findall(r'season-\d+-episode-(\d+)', html, re.I)
            for n in ep_nums:
                if int(n) > max_ep:
                    max_ep = int(n)

            # 2. 從 JSON 欄位（如 "episodeCount": 60 或 "total_episodes": 60 或 "number": 60）找最大集數
            json_nums = re.findall(r'"(?:episode_?count|total_?episodes|episodes_?count|episode_?number|number)"\s*:\s*(\d+)', html, re.I)
            for n in json_nums:
                val = int(n)
                if 1 <= val <= 300 and val > max_ep:
                    max_ep = val

            # 3. 從中文文字（如「全60集」、「共80集」、「更新至45集」）提取總集數
            text_nums = re.findall(r'(?:全|共|更新至|第)\s*(\d+)\s*集', soup.get_text())
            for n in text_nums:
                val = int(n)
                if 1 <= val <= 300 and val > max_ep:
                    max_ep = val

            episodes = []
            if drama_prefix and max_ep > 1:
                for ep in range(1, max_ep + 1):
                    ep_url = f"{drama_prefix}season-{season_num}-episode-{ep}/"
                    episodes.append(f"第{ep}集${ep_url}")
            elif drama_prefix:
                # 若無法偵測到總集數，預設先生成第 1 集（或當前網址）
                first_url = vid if "episode-" in vid else f"{drama_prefix}season-{season_num}-episode-1/"
                episodes.append(f"第1集${first_url}")
            else:
                episodes.append(f"立即播放${vid}")

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "柚子線路",
                "vod_play_url": "#".join(episodes)
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    # 4. 關鍵字搜尋
    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/dramas/?q={requests.utils.quote(key)}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')
            return {"list": self._parse_drama_cards(soup)}
        except Exception:
            return {"list": []}

    # 5. 核心播放解析：訪問該集網址取得專屬 UUID，並呼叫 POST /api/playback/{uuid}?mode=mse&startup=1
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith('http') else f"{self.host}{id}"
        play_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": play_page,
            "Origin": self.host,
            "Accept": "application/json, text/plain, */*"
        }

        candidate_uuids = []
        try:
            resp = requests.get(play_page, headers=play_headers, timeout=10)
            resp.encoding = 'utf-8'
            html = resp.text

            # 優先尋找 JSON 中與當前單集綁定的 episodeId / playbackId / id
            ep_id_matches = re.findall(
                r'"(?:episode_?id|playback_?id|video_?id|id)"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
                html,
                re.I
            )
            for u in ep_id_matches:
                if u not in candidate_uuids:
                    candidate_uuids.append(u)

            # 補充提取頁面內所有其他 UUID 作為備選
            all_uuids = re.findall(
                r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
                html,
                re.I
            )
            for u in all_uuids:
                if u not in candidate_uuids:
                    candidate_uuids.append(u)
        except Exception:
            pass

        # 依序向 /api/playback/{uuid}?mode=mse&startup=1 發送 POST 請求
        for uid in candidate_uuids[:8]:
            api_url = f"{self.host}/api/playback/{uid}?mode=mse&startup=1"
            try:
                r = requests.post(api_url, headers=play_headers, timeout=8)
                if r.status_code == 200:
                    data = r.json()
                    m3u8_path = data.get("url", "")
                    if m3u8_path:
                        stream_url = m3u8_path if m3u8_path.startswith("http") else f"{self.host}{m3u8_path}"
                        stream_headers = {
                            "User-Agent": self.headers["User-Agent"],
                            "Referer": play_page,
                            "Origin": self.host
                        }
                        return {
                            "parse": 0,
                            "playUrl": "",
                            "url": stream_url,
                            "header": json.dumps(stream_headers)
                        }
            except Exception:
                continue

        return {
            "parse": 0,
            "playUrl": "",
            "url": "",
            "header": json.dumps(play_headers)
        }

    # 核心解析：抓取所有指向 /dramas/ 的短劇卡片
    def _parse_drama_cards(self, soup):
        videos = []
        seen_urls = set()

        for a in soup.select('a[href*="/dramas/"]'):
            href = a.get('href', '').strip()
            if href in ('/dramas', '/dramas/') or href in seen_urls:
                continue

            img = a.select_one('img') or (a.parent and a.parent.select_one('img'))
            if not img:
                continue

            pic = img.get('data-src') or img.get('data-original') or img.get('src') or ""
            if pic.startswith('/'):
                pic = self.host + pic

            title_el = a.select_one('h2, h3, h4, [class*="title"], [class*="name"]')
            title = (
                (title_el.get_text(strip=True) if title_el else "")
                or a.get('title', '').strip()
                or img.get('alt', '').strip()
                or a.get_text(strip=True)
            )

            remark_el = a.select_one('[class*="ep"], [class*="badge"], [class*="tag"], span')
            remark = remark_el.get_text(strip=True) if remark_el and remark_el.get_text(strip=True) != title else ""

            if title:
                seen_urls.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })

        return videos

    def localProxy(self, param):
        return [200, "video/MP2T", "", {}]

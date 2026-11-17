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

    # 3. 影片詳情與選集（同時支援分集網頁連結與內嵌 UUID 列表）
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

            episodes = []
            seen_ep = set()

            # 方式 A：抓取同劇集下的分集子頁面連結（如 /dramas/xxx/season-1-episode-1/）
            parts = [p for p in vid.split('/') if p]
            drama_prefix = f"/{parts[0]}/{parts[1]}/" if len(parts) >= 2 else ""

            for a in soup.select('a[href]'):
                href = a.get('href', '').strip()
                ep_text = a.get_text(strip=True)
                if drama_prefix and href.startswith(drama_prefix) and href != drama_prefix and href not in seen_ep:
                    seen_ep.add(href)
                    label = ep_text if ep_text else f"第{len(episodes)+1}集"
                    episodes.append(f"{label}${href}")

            # 方式 B：若分集連結未直接展開在 <a> 標籤中，從頁面腳本提取 /media/{drama_uuid}/{ep_uuid} 列表
            if len(episodes) <= 1:
                media_pairs = re.findall(
                    r'/media/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
                    html,
                    re.I
                )
                unique_pairs = []
                for pair in media_pairs:
                    if pair not in unique_pairs:
                        unique_pairs.append(pair)

                if len(unique_pairs) > 1:
                    episodes = []
                    for idx, (d_uuid, e_uuid) in enumerate(unique_pairs):
                        # 優先將 e_uuid 與 d_uuid 傳給 playerContent 呼叫 /api/playback/
                        episodes.append(f"第{idx+1}集$uuid:{e_uuid}|{d_uuid}")

            if not episodes:
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

    # 5. 核心播放解析：呼叫 POST /api/playback/{uuid}?mode=mse&startup=1 取得 .m3u8
    def playerContent(self, flag, id, vipFlags):
        play_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": self.host + "/",
            "Origin": self.host,
            "Accept": "application/json, text/plain, */*"
        }

        candidate_uuids = []
        play_page = ""

        if id.startswith("uuid:"):
            # 格式為 uuid:{e_uuid}|{d_uuid}
            raw = id.split(":", 1)[1]
            candidate_uuids.extend([u for u in raw.split("|") if u])
        else:
            play_page = id if id.startswith('http') else f"{self.host}{id}"
            play_headers["Referer"] = play_page
            try:
                resp = requests.get(play_page, headers=play_headers, timeout=10)
                resp.encoding = 'utf-8'
                html = resp.text

                # 若頁面內有 /media/{drama_uuid}/{episode_uuid}，優先提取兩個 UUID 依序嘗試 playback API
                media_match = re.search(
                    r'/media/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
                    html,
                    re.I
                )
                if media_match:
                    candidate_uuids.append(media_match.group(2))
                    candidate_uuids.append(media_match.group(1))

                # 補充提取頁面內其他 UUID（例如劇集或單集 ID）
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
        for uid in candidate_uuids[:6]:
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
                            "Referer": play_page or (self.host + "/"),
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

        # 失敗時回傳 parse: 0 空連結，避免 langhuan/spider 殼觸發 MissingPluginException
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

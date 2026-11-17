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
        self.base_cookie = (
            "eden_age_v2=accepted.1794883431.1794969831.rC%2FUb99IEpmeivtisgFBCfvpBX%2B5ut0HN2J9UYzvaGY%3D; "
            "eden_account=fed6f3c03defd79fa12ae79766bbcf3bb1822153343144434752faa4a599d28e; "
            "__Host-eden_analytics=994da745ac4b31de1b5bfe24bf924eba6a8a77c4266a2c85d1f70306ffc5c643"
        )
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": self.host + "/",
            "Origin": self.host,
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Cookie": self.base_cookie
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._init_session()

    def _init_session(self):
        """初始化並刷新訪客/帳號驗證 Cookie"""
        try:
            self.session.get(f"{self.host}/api/viewer", timeout=6)
            self.session.get(f"{self.host}/api/account", timeout=6)
        except Exception:
            pass

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
            resp = self.session.get(self.host, timeout=10)
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
            resp = self.session.get(url, timeout=10)
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

    # 3. 影片詳情與選集
    def detailContent(self, ids):
        vid = ids[0]
        url = vid if vid.startswith('http') else f"{self.host}{vid}"
        try:
            resp = self.session.get(url, timeout=10)
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

            parts = [p for p in vid.split('/') if p]
            drama_prefix = f"/{parts[0]}/{parts[1]}/" if len(parts) >= 2 else ""

            episodes = []
            seen_ep = set()

            if drama_prefix:
                raw_paths = re.findall(rf'({re.escape(drama_prefix)}[a-zA-Z0-9\-_/]+)', html)
                valid_paths = []
                for p in raw_paths:
                    clean_p = p.split('"')[0].split("'")[0].split('\\')[0]
                    if clean_p.rstrip('/') != drama_prefix.rstrip('/') and clean_p not in seen_ep:
                        seen_ep.add(clean_p)
                        num_m = re.search(r'episode-?(\d+)', clean_p, re.I)
                        ep_num = int(num_m.group(1)) if num_m else 9999
                        valid_paths.append((ep_num, clean_p))

                valid_paths.sort(key=lambda x: x[0])
                for idx, (ep_num, path) in enumerate(valid_paths):
                    label = f"第{ep_num}集" if ep_num != 9999 else f"第{idx+1}集"
                    episodes.append(f"{label}${path}")

            if not episodes:
                episodes.append(f"第1集${vid}")

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
            resp = self.session.get(url, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')
            return {"list": self._parse_drama_cards(soup)}
        except Exception:
            return {"list": []}

    # 5. 核心播放解析：帶完整 Cookie 呼叫 POST /api/playback/{uuid}?mode=mse&startup=1
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith('http') else f"{self.host}{id}"
        candidate_uuids = []

        try:
            resp = self.session.get(play_page, headers={"Referer": self.host + "/"}, timeout=10)
            resp.encoding = 'utf-8'
            html = resp.text

            priority_uuids = re.findall(
                r'(?:playback|episode|currentEpisode|video|asset)[^0-9a-f]{0,40}([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})',
                html,
                re.I
            )
            for u in priority_uuids:
                if u not in candidate_uuids:
                    candidate_uuids.append(u)

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

        api_headers = {
            "Referer": play_page,
            "Origin": self.host,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*"
        }

        # 合併 Session 最新取得的所有 Cookies
        current_cookies = "; ".join([f"{k}={v}" for k, v in self.session.cookies.get_dict().items()])
        final_cookie = f"{self.base_cookie}; {current_cookies}" if current_cookies else self.base_cookie

        for uid in candidate_uuids[:25]:
            api_url = f"{self.host}/api/playback/{uid}?mode=mse&startup=1"
            try:
                r = self.session.post(api_url, headers=api_headers, json={}, timeout=6)
                if r.status_code == 200:
                    data = r.json()
                    m3u8_path = data.get("url", "")
                    if m3u8_path:
                        stream_url = m3u8_path if m3u8_path.startswith("http") else f"{self.host}{m3u8_path}"
                        stream_headers = {
                            "User-Agent": self.headers["User-Agent"],
                            "Referer": play_page,
                            "Origin": self.host,
                            "Cookie": final_cookie
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
            "header": json.dumps(api_headers)
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

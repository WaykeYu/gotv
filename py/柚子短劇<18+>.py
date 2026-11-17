# -*- coding: utf-8 -*-
import sys
import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "柚子短劇"

    def init(self, extend=""):
        self.host = "https://youzidj.com"
        self.full_cookie = (
            "eden_age_v2=accepted.1794883431.1794969831.rC%2FUb99IEpmeivtisgFBCfvpBX%2B5ut0HN2J9UYzvaGY%3D; "
            "eden_account=fed6f3c03defd79fa12ae79766bbcf3bb1822153343144434752faa4a599d28e; "
            "__Host-eden_analytics=994da745ac4b31de1b5bfe24bf924eba6a8a77c4266a2c85d1f70306ffc5c643; "
            "eden_analytics_consent=eyJhbmFseXRpY3MiOiJhbGxvd2VkIiwidGhpcmRfcGFydHkiOmZhbHNlLCJyZXBsYXkiOmZhbHNlLCJ2ZXJzaW9uIjoiMjAyNi0xMC0wMyIsImVmZmVjdGl2ZV9hdF9tcyI6MTc5NDg4MzQzMjM1OCwiZXhwaXJlc19hdF9tcyI6MTgyNjQxOTQzMjM1OCwiY29uc2VudF9lcG9jaCI6MX0%3D.fc3f941e905891b58f732b8b7ebd0edb9da1716cbef53a1149d4cd2d99416b38"
        )
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/157.0.0.0 Safari/537.36"
        self.base_headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": self.host + "/",
            "Cookie": self.full_cookie
        }
        self.session = requests.Session()
        self.session.headers.update(self.base_headers)

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

    # 3. 影片詳情與完整選集（第1集保證用真實入口頁，後續集數自動展開並交由 playerContent 容錯解析）
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

            # 偵測總集數
            max_ep = 0
            for n in re.findall(r'season-\d+-episode-(\d+)', html, re.I):
                max_ep = max(max_ep, int(n))
            for n in re.findall(r'"(?:episode_?count|total_?episodes|episodes_?count|episode_?number|number)"\s*:\s*(\d+)', html, re.I):
                val = int(n)
                if 1 <= val <= 300:
                    max_ep = max(max_ep, val)
            for n in re.findall(r'(?:全|共|更新至|第)\s*(\d+)\s*集', soup.get_text()):
                val = int(n)
                if 1 <= val <= 300:
                    max_ep = max(max_ep, val)

            if max_ep <= 1 and drama_prefix:
                max_ep = 60

            episodes = []
            if drama_prefix:
                # 第 1 集直接綁定原始入口網址 vid（保證 200 OK 不會 404）
                episodes.append(f"第1集${vid}")
                # 第 2 集起傳遞劇集主路徑與集數編號，交由 playerContent 自動探測實際路由
                for ep in range(2, max_ep + 1):
                    episodes.append(f"第{ep}集$ep:{drama_prefix}|{ep}")
            else:
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

    # 5. 核心播放解析：自動適配多集路由 + 透過 localProxy 全程帶 Cookie 代理 m3u8/m4s 徹底防 403
    def playerContent(self, flag, id, vipFlags):
        play_page = ""
        html = ""

        if id.startswith("ep:"):
            # 格式為 ep:{drama_prefix}|{ep_num}
            prefix, ep_num = id.split(":", 1)[1].split("|", 1)
            candidate_urls = [
                f"{self.host}{prefix}season-1-episode-{ep_num}/",
                f"{self.host}{prefix}episode-{ep_num}/",
                f"{self.host}{prefix}season-{ep_num}/"
            ]
            for test_u in candidate_urls:
                try:
                    r = self.session.get(test_u, headers={"Referer": self.host + "/"}, timeout=8)
                    if r.status_code == 200:
                        play_page = test_u
                        r.encoding = 'utf-8'
                        html = r.text.replace('\\"', '"')
                        break
                except Exception:
                    continue
        else:
            play_page = id if id.startswith('http') else f"{self.host}{id}"
            try:
                r = self.session.get(play_page, headers={"Referer": self.host + "/"}, timeout=10)
                r.encoding = 'utf-8'
                html = r.text.replace('\\"', '"')
            except Exception:
                pass

        if not html:
            return {"parse": 0, "playUrl": "", "url": "", "header": {}}

        candidate_uuids = []
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

        api_headers = {
            "User-Agent": self.ua,
            "Accept": "*/*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            "Origin": self.host,
            "Referer": play_page,
            "Cookie": self.full_cookie,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }

        for uid in candidate_uuids[:30]:
            api_url = f"{self.host}/api/playback/{uid}?mode=mse&startup=1"
            try:
                r = self.session.post(api_url, headers=api_headers, data="{}", timeout=6)
                if r.status_code == 200:
                    data = r.json()
                    m3u8_path = data.get("url", "")
                    if m3u8_path:
                        stream_url = m3u8_path if m3u8_path.startswith("http") else f"{self.host}{m3u8_path}"
                        # 交由 localProxy 代理並重寫切片路徑，確保所有子請求 100% 帶上完整 Cookie 與 Referer
                        encoded_url = urllib.parse.quote(stream_url, safe='')
                        encoded_ref = urllib.parse.quote(play_page, safe='')
                        proxy_url = f"{self.getProxyUrl()}&url={encoded_url}&ref={encoded_ref}&type=m3u8"
                        return {
                            "parse": 0,
                            "playUrl": "",
                            "url": proxy_url,
                            "header": {}
                        }
            except Exception:
                continue

        return {
            "parse": 0,
            "playUrl": "",
            "url": "",
            "header": {}
        }

    # 本機代理：代為向 youzidj.com 請求 m3u8 與 m4s/mp4 切片（附帶完整 Cookie，徹底消除 HTTP 403）
    def localProxy(self, param):
        target_url = urllib.parse.unquote(param.get("url", ""))
        ref_url = urllib.parse.unquote(param.get("ref", self.host + "/"))
        if not target_url:
            return [404, "text/plain", b"", {}]

        req_headers = {
            "User-Agent": self.ua,
            "Referer": ref_url,
            "Origin": self.host,
            "Cookie": self.full_cookie
        }

        try:
            r = self.session.get(target_url, headers=req_headers, timeout=10)
            if r.status_code != 200:
                return [r.status_code, "text/plain", b"", {}]

            if ".m3u8" in target_url or param.get("type") == "m3u8":
                base_url = target_url.rsplit("/", 1)[0] + "/"
                lines = r.text.splitlines()
                new_lines = []
                for line in lines:
                    line_strip = line.strip()
                    if not line_strip:
                        new_lines.append(line)
                    elif line_strip.startswith("#"):
                        def replace_uri(match):
                            uri = match.group(1)
                            abs_uri = uri if uri.startswith("http") else urllib.parse.urljoin(base_url, uri)
                            p_uri = f"{self.getProxyUrl()}&url={urllib.parse.quote(abs_uri, safe='')}&ref={urllib.parse.quote(ref_url, safe='')}"
                            return f'URI="{p_uri}"'

                        new_line = re.sub(r'URI="([^"]+)"', replace_uri, line_strip)
                        new_lines.append(new_line)
                    else:
                        abs_seg = line_strip if line_strip.startswith("http") else urllib.parse.urljoin(base_url, line_strip)
                        seg_type = "&type=m3u8" if ".m3u8" in abs_seg else ""
                        p_seg = f"{self.getProxyUrl()}&url={urllib.parse.quote(abs_seg, safe='')}&ref={urllib.parse.quote(ref_url, safe='')}{seg_type}"
                        new_lines.append(p_seg)

                m3u8_content = "\n".join(new_lines).encode("utf-8")
                return [200, "application/vnd.apple.mpegurl", m3u8_content, {}]

            content_type = r.headers.get("Content-Type", "video/mp4")
            return [200, content_type, r.content, {}]
        except Exception:
            return [500, "text/plain", b"", {}]

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

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
# 3. 影片詳情與選集（直接於線路名稱顯示第1集 API 測試結果）
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
                use_season_only = bool(re.search(rf'{re.escape(drama_prefix)}season-1/(?!episode)', html, re.I)) and not bool(re.search(r'season-1-episode-\d+', html, re.I))
                if use_season_only:
                    episodes.append(f"第1集${drama_prefix}season-1/")
                else:
                    for ep in range(1, max_ep + 1):
                        ep_url = f"{drama_prefix}season-1-episode-{ep}/"
                        episodes.append(f"第{ep}集${ep_url}")
            else:
                episodes.append(f"第1集${vid}")

            # 現場實測第 1 集網址與 POST playback API 的真實狀態碼
            first_ep_path = episodes[0].split('$')[1]
            first_ep_url = first_ep_path if first_ep_path.startswith('http') else f"{self.host}{first_ep_path}"
            r_ep = self.session.get(first_ep_url, timeout=8)
            ep_uuids = list(dict.fromkeys(re.findall(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', r_ep.text, re.I)))

            api_status = "未測"
            if ep_uuids:
                test_api = f"{self.host}/api/playback/{ep_uuids[0]}?mode=mse&startup=1"
                r_api = self.session.post(
                    test_api,
                    headers={
                        "User-Agent": self.ua,
                        "Content-Type": "application/json",
                        "Origin": self.host,
                        "Referer": first_ep_url,
                        "Cookie": self.full_cookie
                    },
                    data="{}",
                    timeout=6
                )
                api_status = f"{r_api.status_code}:{r_api.text[:25]}"

            diag_tab = f"柚子[頁{r_ep.status_code}|U:{len(ep_uuids)}|API:{api_status}]"

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": diag_tab,
                "vod_play_url": "#".join(episodes)
            }
            return {"list": [vod]}
        except Exception as e:
            return {"list": [{
                "vod_id": vid,
                "vod_name": "錯誤",
                "vod_play_from": f"異常:{str(e)[:30]}",
                "vod_play_url": "第1集$err"
            }]}

        # 將診斷結果寫入網址回傳，避免「没有获取到播放地址」，並可在錯誤畫面或抓包看到狀態
        diag_url = f"http://127.0.0.1/page_{page_status}_uuids_{len(candidate_uuids)}_api_{last_api_status}.m3u8"
        return {
            "parse": 0,
            "playUrl": "",
            "url": diag_url,
            "header": "{}"
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

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

    # 3. 影片詳情與分集
    def detailContent(self, ids):
        vid = ids[0]
        url = vid if vid.startswith('http') else f"{self.host}{vid}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')

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
            # 取得劇集主路徑，例如 /dramas/high-school-love-story/
            parts = [p for p in vid.split('/') if p]
            drama_prefix = f"/{parts[0]}/{parts[1]}/" if len(parts) >= 2 else ""

            for a in soup.select('a[href]'):
                href = a.get('href', '').strip()
                ep_text = a.get_text(strip=True)
                if drama_prefix and href.startswith(drama_prefix) and href != drama_prefix and href not in seen_ep:
                    seen_ep.add(href)
                    label = ep_text if ep_text else f"第{len(episodes)+1}集"
                    episodes.append(f"{label}${href}")

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

    # 5. 解析播放頁真實串流（針對 /media/.../delivery-v2/ 結構）
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith('http') else f"{self.host}{id}"
        play_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": play_page,
            "Origin": self.host
        }

        try:
            resp = requests.get(play_page, headers=play_headers, timeout=10)
            resp.encoding = 'utf-8'
            html = resp.text

            # 優先比對該站特有的 /media/.../delivery-v2/... 主播放清單（.m3u8 或 .mpd）
            delivery_match = re.search(
                r'((?:https?:)?//[^\s"\'\\<>]*/media/[^\s"\'\\<>]+?\.(?:m3u8|mpd)(?:\?[^\s"\'\\<>]*)?|/media/[^\s"\'\\<>]+?\.(?:m3u8|mpd)(?:\?[^\s"\'\\<>]*)?)',
                html
            )
            if delivery_match:
                stream_url = delivery_match.group(1).replace('\\u002F', '/').replace('\\/', '/')
                if stream_url.startswith('//'):
                    stream_url = 'https:' + stream_url
                elif stream_url.startswith('/'):
                    stream_url = self.host + stream_url

                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": stream_url,
                    "header": json.dumps(play_headers)
                }

            # 其次比對其他通用 .m3u8 / .mpd / .mp4（排除 init.mp4 分片）
            generic_match = re.search(
                r'(https?://[^\s"\'\\<>]+?\.(?:m3u8|mpd|mp4)(?:\?[^\s"\'\\<>]*)?)',
                html
            )
            if generic_match:
                stream_url = generic_match.group(1).replace('\\u002F', '/').replace('\\/', '/')
                if not stream_url.endswith('init.mp4'):
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": stream_url,
                        "header": json.dumps(play_headers)
                    }
        except Exception:
            pass

        # 若 token 是由前端 JS 動態請求 API 取得，交由 TVBox WebView 自動執行 JS 並嗅探 .m3u8/.mpd
        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": json.dumps(play_headers)
        }

    # 核心解析：自動抓取所有指向 /dramas/ 的短劇卡片
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

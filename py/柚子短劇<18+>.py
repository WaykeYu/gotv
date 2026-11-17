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
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
        }

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|mkv)(\?|$)', url, re.I))

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

            # 自動從導覽列抓取其他真實分類連結（排除首頁與外部連結）
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
        # 常見現代網站分頁參數（?page=2 或 /page/2/）
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

    # 3. 影片詳情與分集（如 /dramas/high-school-love-story/season-1/）
    def detailContent(self, ids):
        vid = ids[0]
        url = vid if vid.startswith('http') else f"{self.host}{vid}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')

            # 標題
            h1 = soup.select_one('h1')
            title = h1.get_text(strip=True) if h1 else "未知短劇"

            # 封面
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

            # 簡介
            desc = ""
            og_desc = soup.select_one('meta[name="description"], meta[property="og:description"]')
            if og_desc and og_desc.get('content'):
                desc = og_desc.get('content')

            # 尋找該劇的所有集數或季數連結（同前綴路徑下的子連結）
            episodes = []
            seen_ep = set()
            # 取得劇集主路徑，例如 /dramas/high-school-love-story/
            drama_prefix = "/".join(vid.rstrip('/').split('/')[:3])

            for a in soup.select('a[href]'):
                href = a.get('href', '').strip()
                ep_text = a.get_text(strip=True)
                if drama_prefix and href.startswith(drama_prefix) and href != drama_prefix + "/" and href not in seen_ep:
                    seen_ep.add(href)
                    label = ep_text if ep_text else f"第{len(episodes)+1}集"
                    episodes.append(f"{label}${href}")

            # 若該頁面本身就是直接播放頁（單頁切換集數），至少加入當前頁作為第1集
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
        # 嘗試常見搜尋參數 ?q= 或 ?s= 或 /search?q=
        url = f"{self.host}/dramas/?q={requests.utils.quote(key)}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')
            return {"list": self._parse_drama_cards(soup)}
        except Exception:
            return {"list": []}

    # 5. 解析播放頁真實串流（提取 <video>、<source> 或腳本內的 m3u8 / mp4）
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith('http') else f"{self.host}{id}"
        try:
            resp = requests.get(play_page, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            html = resp.text
            soup = BeautifulSoup(html, 'lxml')

            # 方法 A：直接找 HTML5 <video src="..."> 或 <source src="...">
            video_tag = soup.select_one('video source[src], video[src]')
            if video_tag and video_tag.get('src'):
                src = video_tag.get('src')
                if src.startswith('/'):
                    src = self.host + src
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": src,
                    "header": json.dumps(self.headers)
                }

            # 方法 B：從網頁原始碼或 Next.js JSON 資料中正則提取 .m3u8 或 .mp4
            media_match = re.search(r'(https?://[^\s"\'\\<>]+\.(?:m3u8|mp4)(?:\?[^\s"\'\\<>]*)?)', html)
            if media_match:
                real_url = media_match.group(1).replace('\\u002F', '/').replace('\\/', '/')
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": real_url,
                    "header": json.dumps(self.headers)
                }
        except Exception:
            pass

        # 方法 C：交由 TVBox 內建 WebView 嗅探器自動攔截播放請求
        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": json.dumps(self.headers)
        }

    # 核心解析：自動抓取所有指向 /dramas/ 的短劇卡片
    def _parse_drama_cards(self, soup):
        videos = []
        seen_urls = set()

        for a in soup.select('a[href*="/dramas/"]'):
            href = a.get('href', '').strip()
            # 排除純分類首頁 /dramas/ 本身，以及重複連結
            if href in ('/dramas', '/dramas/') or href in seen_urls:
                continue

            # 尋找卡片內的圖片（可能在 <a> 裡面，也可能在父層容器裡）
            img = a.select_one('img') or (a.parent and a.parent.select_one('img'))
            if not img:
                continue

            pic = img.get('data-src') or img.get('data-original') or img.get('src') or ""
            if pic.startswith('/'):
                pic = self.host + pic

            # 提取劇名（優先找標題標籤或 img alt，其次找連結文字）
            title_el = a.select_one('h2, h3, h4, [class*="title"], [class*="name"]')
            title = (
                (title_el.get_text(strip=True) if title_el else "")
                or a.get('title', '').strip()
                or img.get('alt', '').strip()
                or a.get_text(strip=True)
            )

            # 提取集數或標籤（如 "全60集"、"更新至12集"）
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

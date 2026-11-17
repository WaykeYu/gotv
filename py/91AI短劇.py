# coding=utf-8
import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "91AI短劇"

    def init(self, extend=""):
        self.host = "https://91aiporn.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": f"{self.host}/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,zh-CN;q=0.8,en;q=0.7"
        }

    def homeContent(self, filter):
        classes = []
        seen_names = set()

        # 動態從首頁導航欄抓取分類連結
        try:
            res = requests.get(self.host, headers=self.headers, timeout=10)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")
            target_cats = ["AI成人短剧", "国产剧集", "日系漫剧", "中字剧集", "无码剧集"]
            
            for a in soup.find_all("a", href=True):
                name = a.get_text(strip=True)
                href = a.get("href", "").strip()
                if name in target_cats and name not in seen_names and href and href != "/":
                    seen_names.add(name)
                    classes.append({"type_id": href, "type_name": name})
        except Exception:
            pass

        # 若動態抓取失敗，啟用備用常見路徑（請依實際網址微調）
        if not classes:
            fallback = [
                ("/vodtype/1.html", "AI成人短剧"),
                ("/vodtype/2.html", "国产剧集"),
                ("/vodtype/3.html", "日系漫剧"),
                ("/vodtype/4.html", "中字剧集"),
                ("/vodtype/5.html", "无码剧集")
            ]
            for path, name in fallback:
                classes.append({"type_id": path, "type_name": name})

        return {
            "class": classes,
            "filters": {}
        }

    def homeVideoContent(self):
        try:
            res = requests.get(self.host, headers=self.headers, timeout=10)
            res.encoding = "utf-8"
            return {"list": self._parse_videos(res.text, res.status_code)}
        except Exception:
            return {"list": []}

    def _normalize_url(self, href):
        if not href:
            return ""
        if href.startswith("http"):
            return href
        if href.startswith("//"):
            return "https:" + href
        if href.startswith("/"):
            return self.host + href
        return f"{self.host}/{href.lstrip('./')}"

    def _parse_videos(self, html, status_code=200):
        videos = []
        seen_urls = set()
        soup = BeautifulSoup(html, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            # 過濾非影片詳情頁的連結（排除首頁、分類頁、搜尋、登入與圖集）
            if not href or href in ["/", "#"] or any(x in href for x in ["login", "register", "search", "page", "tag", "type", "category", "pic", "photo"]):
                continue
            # 影片詳情頁通常包含數字 ID 或特定路徑（如 /video/、/voddetail/、/watch/ 或純數字 slug）
            if not re.search(r"/(?:video|voddetail|vodplay|watch|play|v|detail)/|/\d+(?:\.html)?/?$", href):
                continue

            full_url = self._normalize_url(href)
            if full_url in seen_urls:
                continue

            # 向上尋找包含完整卡片資訊的父節點
            card = a
            curr = a.parent
            for _ in range(5):
                if not curr or curr.name not in ["div", "article", "li", "section"]:
                    break
                # 避免向上爬升到包含多個影片的列表容器
                if len(curr.find_all("img")) > 2:
                    break
                card = curr
                curr = curr.parent

            # 提取標題
            title = a.get("title", "").strip()
            if not title:
                for tag in card.find_all(["h1", "h2", "h3", "h4", "h5", "p", "span"]):
                    t = tag.get_text(strip=True)
                    # 排除純時長（如 16:25 或 01:12:07）與標籤文字
                    if len(t) >= 3 and not re.match(r"^\d{1,2}:\d{2}(?::\d{2})?$", t) and "查看详情" not in t:
                        title = t
                        break

            if not title:
                img = card.find("img")
                if img and img.get("alt"):
                    title = img.get("alt").strip()

            if not title or len(title) < 2:
                continue

            # 提取封面圖（支援多種常見懶加載屬性）
            pic = ""
            img_el = card.find("img")
            if img_el:
                pic = (
                    img_el.get("data-src")
                    or img_el.get("data-original")
                    or img_el.get("data-lazy-src")
                    or img_el.get("src")
                    or ""
                )
                pic = self._normalize_url(pic)

            # 提取影片時長作為副標題（remarks）
            remarks = ""
            dur_match = re.search(r"\b(\d{1,2}:\d{2}(?::\d{2})?)\b", card.get_text(" ", strip=True))
            if dur_match:
                remarks = dur_match.group(1)

            seen_urls.add(full_url)
            videos.append({
                "vod_id": full_url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks
            })

        # 診斷機制：若未解析出影片，將頁面上抓到的連結樣本顯示在電視盒畫面上以便調整正則
        if not videos:
            sample_hrefs = [a.get("href", "") for a in soup.find_all("a", href=True) if len(a.get("href", "")) > 4][:4]
            videos.append({
                "vod_id": self.host,
                "vod_name": f"[診斷] HTTP:{status_code} | 連結樣本:{','.join(sample_hrefs) or '無'}",
                "vod_pic": "",
                "vod_remarks": f"長度:{len(html)}"
            })

        return videos

    def categoryContent(self, tid, pg, filter, extend):
        base_url = self._normalize_url(tid)
        pg_str = str(pg)

        # 自動適配常見的分頁 URL 格式
        if pg_str == "1":
            url = base_url
        else:
            if ".html" in base_url:
                # 例如 /vodtype/1.html -> /vodtype/1-2.html 或 /vodtype/1/page/2.html
                url = re.sub(r"\.html$", f"-{pg_str}.html", base_url)
            elif "?" in base_url:
                url = f"{base_url}&page={pg_str}"
            else:
                url = f"{base_url.rstrip('/')}/page/{pg_str}/"

        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            res.encoding = "utf-8"
            videos = self._parse_videos(res.text, res.status_code)
        except Exception as e:
            videos = [{
                "vod_id": url,
                "vod_name": f"[連線異常] {str(e)[:40]}",
                "vod_pic": "",
                "vod_remarks": "請求失敗"
            }]

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 99,
            "limit": 24,
            "total": 2376
        }

    def detailContent(self, ids):
        url = ids[0]
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")

            title_el = soup.find("h1") or soup.find("h2")
            title = title_el.get_text(strip=True) if title_el else "未知影片"

            desc_el = soup.find("meta", {"name": "description"})
            desc = desc_el["content"].strip() if desc_el and desc_el.get("content") else ""

            img_el = soup.find("meta", {"property": "og:image"})
            pic = self._normalize_url(img_el["content"]) if img_el and img_el.get("content") else ""
        except Exception:
            title, desc, pic = "未知影片", "", ""

        # 單片直接播放，將詳情頁 URL 傳給 playerContent 解析或嗅探
        play_url = f"立即播放${url}"

        return {"list": [{
            "vod_id": url,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "91AI線路",
            "vod_play_url": play_url
        }]}

    def searchContent(self, key, quick, pg="1"):
        # 嘗試常見搜尋參數格式（若網站搜尋路徑不同，可依據瀏覽器實際搜尋網址修改此行）
        encoded_key = urllib.parse.quote(key)
        url = f"{self.host}/search?q={encoded_key}&page={pg}"
        try:
            res = requests.get(url, headers=self.headers, timeout=10)
            res.encoding = "utf-8"
            return {"list": self._parse_videos(res.text, res.status_code)}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            res = requests.get(id, headers=self.headers, timeout=10)
            res.encoding = "utf-8"
            html = res.text

            # 1. 優先從網頁原始碼或內嵌 JSON 中直接提取 .m3u8 或 .mp4 直鏈
            unescaped = html.replace("\\/", "/")
            m3u8_match = re.search(r'(https?://[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)', unescaped)
            if m3u8_match:
                return {
                    "parse": 0,
                    "url": m3u8_match.group(1),
                    "header": json.dumps(self.headers)
                }
        except Exception:
            pass

        # 2. 若直鏈經過 JS 加密或動態載入，交由 TVBox 內建 WebView 自動嗅探
        return {
            "parse": 1,
            "jx": 0,
            "url": id,
            "header": json.dumps(self.headers)
        }

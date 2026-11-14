# coding=utf-8
import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "楓林網"

    def init(self, extend=""):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
        }
        # 自動追蹤最新跳轉域名
        self.host = "https://imaple.tv"
        for test_url in ["https://imaple.tv/", "https://www.imaple.tv/", "https://imaple.co/"]:
            try:
                r = requests.get(test_url, headers=self.headers, timeout=6, allow_redirects=True)
                if r.status_code == 200 and len(r.text) > 1000:
                    self.host = r.url.rstrip("/")
                    break
            except Exception:
                continue
        self.headers["Referer"] = f"{self.host}/"

    def homeContent(self, filter):
        classes = [
            {"type_id": "2", "type_name": "電視劇"},
            {"type_id": "1", "type_name": "電影"},
            {"type_id": "4", "type_name": "動漫"},
            {"type_id": "3", "type_name": "綜藝"},
            {"type_id": "20", "type_name": "短劇"}
        ]
        return {"class": classes}

    def homeVideoContent(self):
        # 首頁直接抓首頁推薦影片，確保一進入站點就有資料
        res = requests.get(self.host + "/", headers=self.headers, timeout=10)
        return {"list": self._parse_videos(res.text)}

    def categoryContent(self, tid, pg, filter, extend):
        # 輪詢多種常見蘋果CMS / 楓林網分類網址結構
        candidate_urls = [
            f"{self.host}/vodtype/{tid}-{pg}.html",
            f"{self.host}/type/{tid}-{pg}.html",
            f"{self.host}/show/{tid}--------{pg}---.html",
            f"{self.host}/vodshow/{tid}--------{pg}---.html"
        ]
        html = ""
        for u in candidate_urls:
            try:
                res = requests.get(u, headers=self.headers, timeout=8)
                if res.status_code == 200 and len(res.text) > 2000:
                    html = res.text
                    break
            except Exception:
                continue

        videos = self._parse_videos(html)
        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 99,
            "limit": 24,
            "total": 2000
        }

    def _parse_videos(self, html):
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        videos = []

        # 萬能規則：尋找所有包含數字 ID 的詳情頁連結
        for a in soup.find_all("a", href=re.compile(r"/(voddetail|detail|video|movie|tv|drama)/\d+")):
            href = a.get("href", "")
            full_url = href if href.startswith("http") else self.host + href
            
            title = a.get("title", "").strip()
            if not title:
                title_el = a.find(["h2", "h3", "h4", "span", "p"])
                title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            if not title or len(title) < 2 or "播放" in title or "詳情" in title:
                continue

            img = a.find("img") or (a.parent.find("img") if a.parent else None)
            pic = ""
            if img:
                pic = img.get("data-original") or img.get("data-src") or img.get("src") or ""
                if pic and not pic.startswith("http"):
                    pic = self.host + pic

            if not any(v["vod_id"] == full_url for v in videos):
                videos.append({
                    "vod_id": full_url,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return videos

    def detailContent(self, ids):
        url = ids[0]
        res = requests.get(url, headers=self.headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "未知影片"
        desc_el = soup.find("meta", {"name": "description"})
        desc = desc_el["content"] if desc_el else ""

        # 尋找所有包含播放連結 (vodplay / play) 的區塊
        play_links = soup.find_all("a", href=re.compile(r"/(vodplay|play)/"))
        ep_list = []
        for a in play_links:
            ep_name = a.get_text(strip=True)
            ep_href = a.get("href", "")
            if ep_name and ep_href:
                full_ep = ep_href if ep_href.startswith("http") else self.host + ep_href
                ep_list.append(f"{ep_name}${full_ep}")

        vod = {
            "vod_id": url,
            "vod_name": title,
            "vod_pic": "",
            "vod_content": desc,
            "vod_play_from": "楓林網",
            "vod_play_url": "#".join(ep_list) if ep_list else f"立即播放${url}"
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        encoded = urllib.parse.quote(key)
        for u in [
            f"{self.host}/vodsearch/{encoded}----------{pg}---.html",
            f"{self.host}/search/{encoded}----------{pg}---.html",
            f"{self.host}/index.php/vod/search/page/{pg}/wd/{encoded}.html"
        ]:
            try:
                res = requests.get(u, headers=self.headers, timeout=8)
                if res.status_code == 200:
                    vids = self._parse_videos(res.text)
                    if vids:
                        return {"list": vids}
            except Exception:
                continue
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            res = requests.get(id, headers=self.headers, timeout=10)
            player_match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', res.text)
            if player_match:
                pdata = json.loads(player_match.group(1))
                v_url = pdata.get("url", "")
                if v_url and (".m3u8" in v_url or ".mp4" in v_url):
                    return {"parse": 0, "url": v_url, "header": json.dumps(self.headers)}
            m3u8_match = re.search(r'(https?://[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)', res.text)
            if m3u8_match:
                return {"parse": 0, "url": m3u8_match.group(1).replace("\\/", "/"), "header": json.dumps(self.headers)}
        except Exception:
            pass
        return {"parse": 1, "jx": 0, "url": id, "header": json.dumps(self.headers)}

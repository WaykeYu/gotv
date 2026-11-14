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
        self.host = "https://imaple.tv"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": f"{self.host}/",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
        }

    def homeContent(self, filter):
        # 動態從首頁抓取所有分類連結，若失敗則使用預設分類
        classes = []
        try:
            res = requests.get(self.host + "/", headers=self.headers, timeout=8)
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                name = a.get_text(strip=True)
                if re.match(r"^/(category|type|drama|movie|anime|variety|short|list)/[a-zA-Z0-9_-]+$", href) and 1 < len(name) <= 6:
                    if not any(c["type_id"] == href for c in classes):
                        classes.append({"type_id": href, "type_name": name})
        except Exception:
            pass

        if not classes:
            classes = [
                {"type_id": "/", "type_name": "首頁精選"},
                {"type_id": "/drama", "type_name": "電視劇"},
                {"type_id": "/movie", "type_name": "電影"},
                {"type_id": "/anime", "type_name": "動漫"},
                {"type_id": "/variety", "type_name": "綜藝"},
                {"type_id": "/short", "type_name": "短劇"}
            ]
        return {"class": classes}

    def homeVideoContent(self):
        res = requests.get(self.host + "/", headers=self.headers, timeout=10)
        return {"list": self._parse_videos(res.text)}

    def categoryContent(self, tid, pg, filter, extend):
        base_url = self.host if tid == "/" else (tid if tid.startswith("http") else self.host + tid)
        sep = "&" if "?" in base_url else "?"
        url = base_url if str(pg) == "1" else f"{base_url}{sep}page={pg}"

        res = requests.get(url, headers=self.headers, timeout=10)
        videos = self._parse_videos(res.text)
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

        # 精準匹配 CUID 長字串 ID (如 cmwf3xg5o02ftnnn1d10pj0uo) 的作品或播放連結
        for a in soup.find_all("a", href=re.compile(r"/(play|drama|detail|vod|video|movie)/[a-z0-9]{15,35}")):
            href = a.get("href", "")
            # 統一將連結標準化為詳情或播放入口
            full_url = href if href.startswith("http") else self.host + href

            title = a.get("title", "").strip()
            if not title:
                title_el = a.find(["h2", "h3", "h4", "p", "span"])
                title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            if not title or len(title) < 2 or title in ["立即播放", "播放", "詳情"]:
                continue

            img = a.find("img") or (a.parent.find("img") if a.parent else None)
            pic = ""
            if img:
                pic = img.get("data-src") or img.get("data-original") or img.get("src") or ""
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

        img_el = soup.find("meta", {"property": "og:image"})
        pic = img_el["content"] if img_el else ""

        # 提取同部劇的所有集數連結 (/play/{cuid}/{ep})
        cuid_match = re.search(r"/([a-z0-9]{15,35})", url)
        cuid = cuid_match.group(1) if cuid_match else ""

        ep_list = []
        if cuid:
            for a in soup.find_all("a", href=re.compile(rf"/play/{cuid}/\d+")):
                ep_href = a.get("href", "")
                full_ep = ep_href if ep_href.startswith("http") else self.host + ep_href
                ep_name = a.get_text(strip=True) or f"第{len(ep_list)+1}集"
                if not any(full_ep in item for item in ep_list):
                    ep_list.append(f"{ep_name}${full_ep}")

        # 若該頁僅有單集或集數由前端 JS 動態生成，至少保留當前播放頁
        if not ep_list:
            play_target = url if "/play/" in url else f"{self.host}/play/{cuid}/1" if cuid else url
            ep_list.append(f"第1集${play_target}")

        vod = {
            "vod_id": url,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "楓林網(光速線路)",
            "vod_play_url": "#".join(ep_list)
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        encoded = urllib.parse.quote(key)
        for u in [
            f"{self.host}/search?q={encoded}&page={pg}",
            f"{self.host}/search/{encoded}?page={pg}"
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
        # 1. 嘗試直接從頁面原始碼或 Next.js JSON payload 提取 .m3u8 直鏈
        try:
            res = requests.get(id, headers=self.headers, timeout=10)
            m3u8_match = re.search(r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)', res.text)
            if m3u8_match:
                return {
                    "parse": 0,
                    "url": m3u8_match.group(1).replace("\\/", "/"),
                    "header": json.dumps(self.headers)
                }
        except Exception:
            pass

        # 2. 交由 TVBox WebView 自動嗅探實際 .m3u8 串流
        return {
            "parse": 1,
            "jx": 0,
            "url": id,
            "header": json.dumps(self.headers)
        }

# coding=utf-8
import re
import json
import urllib.parse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from base.spider import Spider


class Spider(Spider):
    # 預編譯正則表達式，避免每次解析重複編譯
    CAT_PATTERN = re.compile(r"^/(category|type|drama|movie|anime|variety|short|list)/[a-zA-Z0-9_-]+$")
    VOD_PATTERN = re.compile(r"/(play|drama|detail|vod|video|movie)/([a-z0-9]{15,35})")
    CUID_PATTERN = re.compile(r"/([a-z0-9]{15,35})")
    M3U8_PATTERN = re.compile(r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)')

    INVALID_TITLES = {"立即播放", "播放", "詳情", "更多", "查看詳情"}

    def getName(self):
        return "楓林網"

    def init(self, extend=""):
        self.host = "https://imaple.tv"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": f"{self.host}/",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        }

        # 建立帶有連線池與自動重試機制的 Session
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        retry_strategy = Retry(
            total=2,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _fetch_html(self, url, timeout=10):
        """統一的 HTTP GET 請求封裝，包含狀態碼檢查與例外捕獲"""
        try:
            res = self.session.get(url, timeout=timeout)
            res.raise_for_status()
            res.encoding = res.apparent_encoding or "utf-8"
            return res.text
        except requests.RequestException:
            return ""

    def _abs_url(self, path):
        """安全轉換為絕對路徑"""
        if not path:
            return ""
        return urllib.parse.urljoin(self.host + "/", path)

    def homeContent(self, filter):
        classes = []
        seen_ids = set()
        html = self._fetch_html(self.host + "/", timeout=8)

        if html:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "").strip()
                name = a.get_text(strip=True)
                if self.CAT_PATTERN.match(href) and 1 < len(name) <= 6 and href not in seen_ids:
                    seen_ids.add(href)
                    classes.append({"type_id": href, "type_name": name})

        if not classes:
            classes = [
                {"type_id": "/", "type_name": "首頁精選"},
                {"type_id": "/drama", "type_name": "電視劇"},
                {"type_id": "/movie", "type_name": "電影"},
                {"type_id": "/anime", "type_name": "動漫"},
                {"type_id": "/variety", "type_name": "綜藝"},
                {"type_id": "/short", "type_name": "短劇"},
            ]
        return {"class": classes}

    def homeVideoContent(self):
        # 直接復用 categoryContent 首頁邏輯，減少重複程式碼
        data = self.categoryContent("/", "1", False, {})
        return {"list": data.get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        base_url = self.host + "/" if tid == "/" else self._abs_url(tid)
        sep = "&" if "?" in base_url else "?"
        url = base_url if str(pg) == "1" else f"{base_url}{sep}page={pg}"

        html = self._fetch_html(url, timeout=10)
        videos = self._parse_videos(html)
        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 99 if videos else int(pg),
            "limit": 24,
            "total": 2000,
        }

    def _parse_videos(self, html):
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        videos = []
        seen_urls = set()

        for a in soup.find_all("a", href=self.VOD_PATTERN):
            href = a.get("href", "").strip()
            full_url = self._abs_url(href)
            if full_url in seen_urls:
                continue

            title = a.get("title", "").strip()
            if not title:
                title_el = a.find(["h2", "h3", "h4", "p", "span"])
                title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)

            if not title or len(title) < 2 or title in self.INVALID_TITLES:
                continue

            img = a.find("img") or (a.parent.find("img") if a.parent else None)
            pic = ""
            if img:
                raw_pic = img.get("data-src") or img.get("data-original") or img.get("src") or ""
                pic = self._abs_url(raw_pic)

            # 嘗試提取更新狀態或集數標籤（如：更新至第12集、HD）
            remarks_el = a.find(class_=re.compile(r"(badge|tag|remark|status|ep|update)", re.I))
            remarks = remarks_el.get_text(strip=True) if remarks_el else ""

            seen_urls.add(full_url)
            videos.append({
                "vod_id": full_url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return videos

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        url = self._abs_url(ids[0])
        html = self._fetch_html(url, timeout=10)
        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")

        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else "未知影片"

        desc_el = soup.find("meta", {"name": "description"})
        desc = desc_el.get("content", "").strip() if desc_el else ""

        img_el = soup.find("meta", {"property": "og:image"})
        pic = self._abs_url(img_el.get("content", "").strip()) if img_el else ""

        cuid_match = self.CUID_PATTERN.search(url)
        cuid = cuid_match.group(1) if cuid_match else ""

        ep_list = []
        seen_eps = set()
        if cuid:
            ep_pattern = re.compile(rf"/play/{re.escape(cuid)}/\d+")
            for a in soup.find_all("a", href=ep_pattern):
                full_ep = self._abs_url(a.get("href", "").strip())
                if full_ep in seen_eps:
                    continue
                seen_eps.add(full_ep)
                ep_name = a.get_text(strip=True) or f"第{len(ep_list) + 1}集"
                ep_list.append(f"{ep_name}${full_ep}")

        if not ep_list:
            play_target = url if "/play/" in url else (f"{self.host}/play/{cuid}/1" if cuid else url)
            ep_list.append(f"第1集${play_target}")

        vod = {
            "vod_id": url,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "楓林網",
            "vod_play_url": "#".join(ep_list),
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        encoded = urllib.parse.quote(key)
        candidates = [
            f"{self.host}/search?q={encoded}&page={pg}",
            f"{self.host}/search/{encoded}?page={pg}",
        ]
        for u in candidates:
            html = self._fetch_html(u, timeout=8)
            if html:
                vids = self._parse_videos(html)
                if vids:
                    return {"list": vids}
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        target_url = self._abs_url(id)
        html = self._fetch_html(target_url, timeout=10)
        if html:
            m3u8_match = self.M3U8_PATTERN.search(html)
            if m3u8_match:
                clean_url = m3u8_match.group(1).replace("\\/", "/")
                return {
                    "parse": 0,
                    "url": clean_url,
                    "header": json.dumps(self.headers),
                }

        return {
            "parse": 1,
            "jx": 0,
            "url": target_url,
            "header": json.dumps(self.headers),
        }

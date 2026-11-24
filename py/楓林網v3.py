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
    # 排除非分類的功能性路徑關鍵字
    EXCLUDE_CAT_PATHS = re.compile(
        r"^/(play|detail|vod|video|watch|v|show|search|login|register|user|api|pi|_next|static|about|privacy|terms|dmca|history|favorite)(/|$|\?)",
        re.I,
    )
    # 影片詳情/播放路徑特徵（包含長字串 CUID 或純數字 ID）
    VOD_PATTERN = re.compile(r"/(play|drama|detail|vod|video|movie|watch|v|show)/([a-zA-Z0-9_-]{6,45})")
    CUID_PATTERN = re.compile(r"/([a-zA-Z0-9_-]{10,45})")
    M3U8_PATTERN = re.compile(r'(https?://[^\s"\'<>\\]+\.m3u8[^\s"\'<>\\]*)')

    INVALID_TITLES = {
        "立即播放", "播放", "詳情", "更多", "查看詳情", "LOGO", "logo",
        "登入", "註冊", "搜尋", "歷史", "收藏", "排行榜", "最新", "熱門"
    }
    INVALID_CAT_NAMES = {
        "首頁", "更多", "全部", "登入", "註冊", "搜尋", "歷史", "收藏", "留言", "求片", "APP", "下載", "排行榜"
    }

    def getName(self):
        return "楓林網"

    def init(self, extend=""):
        self.host = "https://imaple.tv"
        if isinstance(extend, str) and extend.strip().startswith("http"):
            self.host = extend.strip().rstrip("/")
        elif isinstance(extend, dict) and extend.get("host"):
            self.host = str(extend["host"]).strip().rstrip("/")

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": f"{self.host}/",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        }

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
        try:
            res = self.session.get(url, timeout=timeout, allow_redirects=True)
            res.encoding = res.apparent_encoding or "utf-8"
            return res.text, str(res.status_code)
        except requests.RequestException as e:
            return "", f"ERR:{type(e).__name__}"

    def _abs_url(self, path):
        if not path:
            return ""
        if path.startswith("//"):
            return "https:" + path
        return urllib.parse.urljoin(self.host + "/", path)

    def _format_pic(self, raw_pic):
        if not raw_pic or raw_pic.startswith("data:image"):
            return ""
        full_pic = self._abs_url(raw_pic.strip())
        return f"{full_pic}@Referer={self.host}/"

    def homeContent(self, filter):
        classes = []
        seen_ids = set()
        seen_names = set()
        html, _ = self._fetch_html(self.host + "/", timeout=8)

        if html:
            soup = BeautifulSoup(html, "html.parser")
            # 優先從 header / nav 導覽列抓取，再掃描全頁其他分類連結
            nav_areas = soup.find_all(["header", "nav"]) or [soup]
            search_pools = nav_areas + [soup]

            for pool in search_pools:
                for a in pool.find_all("a", href=True):
                    href = a.get("href", "").strip()
                    name = a.get_text(strip=True)

                    # 轉換站內完整網址為相對路徑以統一判斷
                    if href.startswith(self.host):
                        href = href[len(self.host):] or "/"

                    if not href.startswith("/") or href == "/" or href.startswith("//"):
                        continue
                    if self.EXCLUDE_CAT_PATHS.match(href):
                        continue
                    # 排除單部影片詳情頁（通常 ID 長度 >= 12）
                    if re.search(r"/[a-zA-Z0-9_-]{12,45}$", href.split("?")[0]):
                        continue

                    if 1 <= len(name) <= 10 and name not in self.INVALID_CAT_NAMES:
                        if href not in seen_ids and name not in seen_names:
                            seen_ids.add(href)
                            seen_names.add(name)
                            classes.append({"type_id": href, "type_name": name})

        # 若動態抓取到的分類太少，補齊常見核心分類（含電視劇與細分地區劇集）
        fallback_classes = [
            {"type_id": "/drama", "type_name": "電視劇"},
            {"type_id": "/movie", "type_name": "電影"},
            {"type_id": "/anime", "type_name": "動漫"},
            {"type_id": "/variety", "type_name": "綜藝"},
            {"type_id": "/short", "type_name": "短劇"},
            {"type_id": "/drama?area=kr", "type_name": "韓劇"},
            {"type_id": "/drama?area=cn", "type_name": "陸劇"},
            {"type_id": "/drama?area=us", "type_name": "美劇"},
            {"type_id": "/drama?area=jp", "type_name": "日劇"},
            {"type_id": "/drama?area=tw", "type_name": "台劇"},
        ]

        if not classes:
            classes = fallback_classes
        else:
            # 確保「電視劇」一定存在於列表中
            if not any("劇" in c["type_name"] for c in classes):
                classes.insert(0, {"type_id": "/drama", "type_name": "電視劇"})

        return {"class": classes}

    def homeVideoContent(self):
        data = self.categoryContent("/", "1", False, {})
        return {"list": data.get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        # 針對常見分類（特別是 /drama 電視劇），準備多組候選路徑以防網站使用 /type/drama 或 /category/drama
        candidate_tids = [tid]
        clean_tid = tid.strip("/")
        if clean_tid and "/" not in clean_tid and "?" not in clean_tid:
            candidate_tids.extend([
                f"/type/{clean_tid}",
                f"/category/{clean_tid}",
                f"/list/{clean_tid}",
                f"/channel/{clean_tid}",
            ])

        videos = []
        last_url = self.host + "/"
        last_status = "200"

        for current_tid in candidate_tids:
            base_url = self.host + "/" if current_tid == "/" else self._abs_url(current_tid)
            sep = "&" if "?" in base_url else "?"
            url = base_url if str(pg) == "1" else f"{base_url}{sep}page={pg}"
            last_url = url

            html, status = self._fetch_html(url, timeout=10)
            last_status = status
            if html and status == "200":
                videos = self._parse_videos(html)
                if videos:
                    break

        if not videos and str(pg) == "1":
            videos.append({
                "vod_id": last_url,
                "vod_name": f"[狀態:{last_status}] 分類無資料 ({tid})",
                "vod_pic": "",
                "vod_remarks": "請檢查分類路徑",
            })

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 99 if len(videos) > 1 else int(pg),
            "limit": 24,
            "total": 2000,
        }

    def _parse_videos(self, html):
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        videos = []
        seen_urls = set()

        # 策略 1：以帶有 alt 的海報 <img> 為核心定位卡片（精準對齊 <img src="/pi/..." alt="片名">）
        for img in soup.find_all("img", alt=True):
            title = img.get("alt", "").strip()
            raw_pic = (
                img.get("src")
                or img.get("data-src")
                or img.get("data-original")
                or img.get("data-lazy-src")
                or ""
            ).strip()

            if not title or len(title) < 2 or title in self.INVALID_TITLES:
                continue
            if not raw_pic or raw_pic.startswith("data:image"):
                continue

            # 往上尋找包覆此圖片的 <a>，或同層卡片容器內的 <a>
            a = img.find_parent("a", href=True)
            if not a:
                card = img.find_parent(["div", "li", "article"])
                if card:
                    a = card.find("a", href=True)
            if not a:
                continue

            href = a.get("href", "").strip()
            if not href or href == "/" or href.startswith("#") or self.EXCLUDE_CAT_PATHS.match(href):
                continue

            full_url = self._abs_url(href)
            if full_url in seen_urls:
                continue

            # 提取集數或畫質狀態標籤
            container = a if a.find("img") else (img.find_parent(["div", "li", "article"]) or a)
            remarks = ""
            for span in container.find_all(["span", "div", "p"], limit=10):
                txt = span.get_text(strip=True)
                if (
                    txt
                    and txt != title
                    and len(txt) <= 18
                    and any(k in txt for k in ["集", "全", "HD", "BD", "更新", "完結", "期", "第", "分", "國語", "粵語", "中字"])
                ):
                    remarks = txt
                    break

            seen_urls.add(full_url)
            videos.append({
                "vod_id": full_url,
                "vod_name": title,
                "vod_pic": self._format_pic(raw_pic),
                "vod_remarks": remarks,
            })

        # 策略 2：傳統 <a> 標籤匹配兜底
        if not videos:
            for a in soup.find_all("a", href=self.VOD_PATTERN):
                href = a.get("href", "").strip()
                full_url = self._abs_url(href)
                if full_url in seen_urls:
                    continue

                img = a.find("img") or (a.parent.find("img") if a.parent else None)
                title = (img.get("alt", "").strip() if img else "") or a.get("title", "").strip()
                if not title:
                    title_el = a.find(["h2", "h3", "h4", "p", "span"])
                    title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)

                if not title or len(title) < 2 or title in self.INVALID_TITLES:
                    continue

                raw_pic = ""
                if img:
                    raw_pic = img.get("src") or img.get("data-src") or img.get("data-original") or ""

                seen_urls.add(full_url)
                videos.append({
                    "vod_id": full_url,
                    "vod_name": title,
                    "vod_pic": self._format_pic(raw_pic),
                    "vod_remarks": "",
                })

        return videos

    def detailContent(self, ids):
        if not ids:
            return {"list": []}

        url = self._abs_url(ids[0])
        html, _ = self._fetch_html(url, timeout=10)
        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")

        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else "未知影片"

        desc_el = soup.find("meta", {"name": "description"})
        desc = desc_el.get("content", "").strip() if desc_el else ""

        img_el = soup.find("meta", {"property": "og:image"})
        raw_pic = img_el.get("content", "").strip() if img_el else ""
        if not raw_pic:
            cover_img = soup.find("img", alt=title)
            if cover_img:
                raw_pic = cover_img.get("src", "")

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
            "vod_pic": self._format_pic(raw_pic),
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
            html, _ = self._fetch_html(u, timeout=8)
            if html:
                vids = self._parse_videos(html)
                if vids:
                    return {"list": vids}
        return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        target_url = self._abs_url(id)
        html, _ = self._fetch_html(target_url, timeout=10)
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

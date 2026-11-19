# -*- coding: utf-8 -*-
import re
import json
import time
import gzip
import urllib.request
import urllib.parse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider:
        def init(self, extend=""): pass
        def homeContent(self, filter): return {}
        def categoryContent(self, tid, pg, filter, extend): return {}
        def detailContent(self, ids): return {}
        def searchContent(self, key, quick, pg=1): return {}
        def playerContent(self, flag, id, vipFlags): return {}
        def localProxy(self, param): return [404, "text/plain", ""]
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def getName(self): return ""


class Spider(BaseSpider):

    def init(self, extend=""):
        # 1. 網域列表（主網域 + 備用網域，可透過 extend 參數傳入自訂網域覆蓋）
        self.domains = [
            "https://xtu.qzjp6.ink",
            "https://qzjp6.ink",
            "https://www.qzjp6.ink",
        ]
        if extend and extend.startswith("http"):
            self.domains.insert(0, extend.rstrip("/"))

        self.active_domain = self.domains[0]
        self.domain_checked = False
        self.webPrefix = "/cn/home/web"

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": f"{self.active_domain}{self.webPrefix}/",
            "Accept-Encoding": "gzip, deflate",
        }

        # 2. 初始化 requests.Session 連線池
        if HAS_REQUESTS:
            self.session = requests.Session()
            self.session.headers.update(self.headers)
        else:
            self.session = None

        # 3. 記憶體快取池: { cache_key: (expire_timestamp, data) }
        self._cache = {}
        self.cache_ttl = 300  # 快取有效時間：300 秒 (5 分鐘)

    def getName(self):
        return "茄子精品"

    # ==================== 快取管理 ====================
    def _get_cache(self, key):
        item = self._cache.get(key)
        if item:
            expire_at, data = item
            if time.time() < expire_at:
                return data
            del self._cache[key]
        return None

    def _set_cache(self, key, data):
        # 限制快取最大條目數，避免長期運行佔用過多記憶體
        if len(self._cache) >= 100:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = (time.time() + self.cache_ttl, data)

    # ==================== 網域健康檢查與請求 ====================
    def _raw_get(self, url, timeout=10):
        """底層 HTTP GET，優先使用 requests.Session，失敗或無模組時降級 urllib"""
        if self.session:
            resp = self.session.get(url, timeout=timeout)
            resp.raise_for_status()
            resp.encoding = "utf-8"
            return resp.text
        else:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_data = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    raw_data = gzip.decompress(raw_data)
                return raw_data.decode("utf-8", errors="ignore")

    def _fetch_html(self, path, use_cache=False, timeout=10):
        """
        帶快取與網域自動故障轉移的請求封裝
        :param path: 相對路徑，例如 '/cn/home/web/index.php/...'
        """
        if use_cache:
            cached = self._get_cache(path)
            if cached is not None:
                return cached

        # 排列網域順序：優先嘗試目前鎖定的健康網域
        candidate_domains = [self.active_domain] + [
            d for d in self.domains if d != self.active_domain
        ]

        for domain in candidate_domains:
            full_url = f"{domain}{path}"
            try:
                # 更新 Referer 匹配當前測試網域
                current_referer = f"{domain}{self.webPrefix}/"
                self.headers["Referer"] = current_referer
                if self.session:
                    self.session.headers["Referer"] = current_referer

                html = self._raw_get(full_url, timeout=timeout)
                if html and ("fed-list-item" in html or "player_data" in html or "</html>" in html.lower()):
                    # 鎖定可用網域
                    if self.active_domain != domain:
                        print(f"[{self.getName()}] 網域切換成功: {domain}")
                        self.active_domain = domain
                    if use_cache:
                        self._set_cache(path, html)
                    return html
            except Exception as e:
                print(f"[{self.getName()}] 網域 {domain} 請求失敗: {e}")
                continue

        return ""

    def _fix_url(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.active_domain + url
        return url

    # ==================== HTML 解析 ====================
    def _parse_vod_list(self, html):
        video_list = []
        blocks = re.findall(r'<li[^>]*class="[^"]*fed-list-item[^"]*"[^>]*>(.*?)</li>', html, re.S)

        for block in blocks:
            href_m = re.search(r'<a[^>]*class="[^"]*fed-list-pics[^"]*"[^>]*href="([^"]+)"', block)
            if not href_m:
                continue
            href = href_m.group(1)
            vid_m = re.search(r'/id/(\d+)', href)
            vid = vid_m.group(1) if vid_m else href

            pic_m = re.search(r'data-original="([^"]+)"', block) or re.search(r'<img[^>]*src="([^"]+)"', block)
            pic = self._fix_url(pic_m.group(1)) if pic_m else ""

            title_m = re.search(r'<a[^>]*class="[^"]*fed-list-title[^"]*"[^>]*>(.*?)</a>', block, re.S)
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else "未知標題"

            rem_m = re.search(r'<span[^>]*class="[^"]*fed-list-remarks[^"]*"[^>]*>(.*?)</span>', block, re.S)
            remarks = re.sub(r'<[^>]+>', '', rem_m.group(1)).strip() if rem_m else ""

            video_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return video_list

    # ==================== 核心介面實作 ====================
    def homeContent(self, filter):
        class_parse = [
            {"type_name": "美女写真", "type_id": "20"},
            {"type_name": "国产精品", "type_id": "21"},
            {"type_name": "无码专区", "type_id": "22"},
            {"type_name": "中文字幕", "type_id": "23"},
            {"type_name": "强奸乱伦", "type_id": "24"},
            {"type_name": "人妻熟女", "type_id": "25"},
            {"type_name": "亚洲情色", "type_id": "26"},
            {"type_name": "制服丝袜", "type_id": "27"},
            {"type_name": "SM捆绑", "type_id": "28"},
            {"type_name": "自淫系列", "type_id": "29"},
            {"type_name": "三级伦理", "type_id": "30"},
        ]

        # 為每個分類配置 MacCMS 標準篩選器（排序方式）
        sort_filter = {
            "key": "by",
            "name": "排序",
            "value": [
                {"n": "最新更新", "v": "time"},
                {"n": "最多播放", "v": "hits"},
                {"n": "最高评分", "v": "score"},
            ]
        }
        filters = {item["type_id"]: [sort_filter] for item in class_parse}

        # 載入首頁推薦列表（啟用快取）
        home_data = self.categoryContent("20", 1, False, {})
        return {
            "class": class_parse,
            "filters": filters,
            "list": home_data.get("list", [])
        }

    def categoryContent(self, tid, pg, filter, extend):
        pg_int = int(pg)
        sort_by = extend.get("by", "") if isinstance(extend, dict) else ""

        # 若有指定排序條件，使用 MacCMS 的 vod/show 篩選路由；否則使用 vod/type 路由
        if sort_by and sort_by != "time":
            path = f"{self.webPrefix}/index.php/vod/show/by/{sort_by}/id/{tid}/page/{pg_int}.html"
        else:
            if pg_int > 1:
                path = f"{self.webPrefix}/index.php/vod/type/id/{tid}-{pg_int}.html"
            else:
                path = f"{self.webPrefix}/index.php/vod/type/id/{tid}.html"

        html = self._fetch_html(path, use_cache=True)
        video_list = self._parse_vod_list(html)

        pagecount = 100
        page_m = re.search(r'(?:/id/\d+-|/page/)(\d+)\.html"[^>]*>尾页', html)
        if page_m:
            pagecount = int(page_m.group(1))

        return {
            "list": video_list,
            "page": pg_int,
            "pagecount": pagecount,
            "limit": len(video_list) or 20,
            "total": pagecount * (len(video_list) or 20),
        }

    def detailContent(self, ids):
        vid = str(ids[0])
        path = f"{self.webPrefix}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        # 詳情頁不快取或短快取，確保 m3u8 token 時效性
        html = self._fetch_html(path, use_cache=False)

        m3u8_url = ""
        player_m = re.search(r'player_data\s*=\s*(\{.*?\});', html, re.S)
        if player_m:
            try:
                p_data = json.loads(player_m.group(1))
                m3u8_url = p_data.get("url", "").replace("\\/", "/")
            except json.JSONDecodeError:
                pass

        if not m3u8_url:
            m3u8_m = re.search(r'"url"\s*:\s*"(https?:\\?/\\?/[^"]+\.m3u8[^"]*)"', html)
            if m3u8_m:
                m3u8_url = m3u8_m.group(1).replace("\\/", "/")

        title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else vid

        play_url = f"第1集${m3u8_url}" if m3u8_url else ""

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": "",
                "vod_remarks": "",
                "vod_content": "",
                "vod_play_from": "高清线路",
                "vod_play_url": play_url,
            }]
        }

    def searchContent(self, key, quick, pg=1):
        pg_int = int(pg)
        encoded_key = urllib.parse.quote(key)
        path = f"{self.webPrefix}/index.php/vod/search/page/{pg_int}/wd/{encoded_key}.html"
        html = self._fetch_html(path, use_cache=True)
        video_list = self._parse_vod_list(html)

        return {
            "list": video_list,
            "page": pg_int,
            "pagecount": 10 if len(video_list) >= 10 else pg_int,
            "limit": 20,
            "total": len(video_list),
        }

    def playerContent(self, flag, id, vipFlags):
        return {
            "parse": 0,
            "jx": 0,
            "url": id,
            "header": {
                "User-Agent": self.headers["User-Agent"],
                "Referer": f"{self.active_domain}{self.webPrefix}/",
            }
        }

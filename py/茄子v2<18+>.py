# -*- coding: utf-8 -*-
import re
import json
import gzip
import urllib.request
import urllib.parse

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
        # 統一使用根網域，避免路徑重複拼接
        self.baseUrl = "https://xtu.qzjp6.ink"
        self.webPrefix = "/cn/home/web"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": f"{self.baseUrl}{self.webPrefix}/",
            "Accept-Encoding": "gzip, deflate",
        }

    def getName(self):
        return "茄子精品"

    def _fetch_html(self, url, timeout=12):
        """統一網路請求封裝，處理超時、異常與 Gzip 壓縮"""
        try:
            req = urllib.request.Request(url, headers=self.headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw_data = resp.read()
                if resp.info().get("Content-Encoding") == "gzip":
                    raw_data = gzip.decompress(raw_data)
                return raw_data.decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"[{self.getName()}] Request Error ({url}): {e}")
            return ""

    def _fix_url(self, url):
        """補全相對路徑的圖片或連結"""
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.baseUrl + url
        return url

    def _parse_vod_list(self, html):
        """按區塊獨立解析影片列表，避免屬性順序變動導致正則失效"""
        video_list = []
        # 匹配每個列表項區塊
        blocks = re.findall(r'<li[^>]*class="[^"]*fed-list-item[^"]*"[^>]*>(.*?)</li>', html, re.S)
        
        for block in blocks:
            # 1. 提取連結與影片 ID
            href_m = re.search(r'<a[^>]*class="[^"]*fed-list-pics[^"]*"[^>]*href="([^"]+)"', block)
            if not href_m:
                continue
            href = href_m.group(1)
            vid_m = re.search(r'/id/(\d+)', href)
            vid = vid_m.group(1) if vid_m else href

            # 2. 提取封面圖（兼容 data-original 與 src）
            pic_m = re.search(r'data-original="([^"]+)"', block) or re.search(r'<img[^>]*src="([^"]+)"', block)
            pic = self._fix_url(pic_m.group(1)) if pic_m else ""

            # 3. 提取標題
            title_m = re.search(r'<a[^>]*class="[^"]*fed-list-title[^"]*"[^>]*>(.*?)</a>', block, re.S)
            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else "未知標題"

            # 4. 提取備註（時長或畫質標籤）
            rem_m = re.search(r'<span[^>]*class="[^"]*fed-list-remarks[^"]*"[^>]*>(.*?)</span>', block, re.S)
            remarks = re.sub(r'<[^>]+>', '', rem_m.group(1)).strip() if rem_m else ""

            video_list.append({
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })
        return video_list

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
        # 預設載入第一個分類的內容作為首頁推薦，避免首頁空白
        home_data = self.categoryContent("20", 1, False, {})
        return {
            "class": class_parse,
            "filters": {},
            "list": home_data.get("list", [])
        }

    def categoryContent(self, tid, pg, filter, extend):
        pg_int = int(pg)
        if pg_int > 1:
            url = f"{self.baseUrl}{self.webPrefix}/index.php/vod/type/id/{tid}-{pg_int}.html"
        else:
            url = f"{self.baseUrl}{self.webPrefix}/index.php/vod/type/id/{tid}.html"

        html = self._fetch_html(url)
        video_list = self._parse_vod_list(html)

        # 動態提取總頁數（若頁面有分頁資訊）
        pagecount = 100
        page_m = re.search(r'/id/\d+-(\d+)\.html"[^>]*>尾页', html)
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
        url = f"{self.baseUrl}{self.webPrefix}/index.php/vod/play/id/{vid}/sid/1/nid/1.html"
        html = self._fetch_html(url)

        # 解析 player_data JSON 物件，比單純匹配字串更可靠
        m3u8_url = ""
        player_m = re.search(r'player_data\s*=\s*(\{.*?\});', html, re.S)
        if player_m:
            try:
                p_data = json.loads(player_m.group(1))
                m3u8_url = p_data.get("url", "").replace("\\/", "/")
            except json.JSONDecodeError:
                pass

        # 備用正則提取
        if not m3u8_url:
            m3u8_m = re.search(r'"url"\s*:\s*"(https?:\\?/\\?/[^"]+\.m3u8[^"]*)"', html)
            if m3u8_m:
                m3u8_url = m3u8_m.group(1).replace("\\/", "/")

        title_m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip() if title_m else vid

        # 標準格式為 "劇集名稱$播放地址"
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
        # 蘋果CMS (MacCMS) 標準搜尋路徑
        url = f"{self.baseUrl}{self.webPrefix}/index.php/vod/search/page/{pg_int}/wd/{encoded_key}.html"
        html = self._fetch_html(url)
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
                "Referer": self.headers["Referer"],
            }
        }

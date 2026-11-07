# -*- coding: utf-8 -*-
"""
愛迪影視爬蟲外掛 (愛迪影視.py)
站點: https://aidi.tv/
適用平台: TVBox / CatVod / FongMi
"""
import os
import re
import json
import time
import base64
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getName(self): return ''
        def init(self, extend=''): pass
        def homeContent(self, filter=False): return {"class": [], "list": [], "filters": {}}
        def homeVideoContent(self): return {"list": []}
        def categoryContent(self, tid, pg, filter=False, extend=''): return {"list": []}
        def detailContent(self, ids): return {"list": []}
        def searchContent(self, key, quick, pg='1'): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None): return {"parse": 0, "url": ""}
        def localProxy(self, param=''): return {}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def destroy(self): pass


class Spider(BaseSpider):
    site_url = "https://aidi.tv"
    base_url = "https://aidi.tv"
    debug = False
    timeout = 15

    def _log(self, *args):
        if self.debug:
            print("[aidi.tv]", *args)

    def _headers(self, referer=None):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Connection": "keep-alive",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "same-origin",
        }
        headers["Referer"] = referer or (self.base_url + "/")
        return headers

    def _fetch(self, path, referer=None, retries=2):
        if not path.startswith("http"):
            url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        else:
            url = path

        for attempt in range(retries):
            try:
                r = requests.get(url, headers=self._headers(referer), timeout=self.timeout, allow_redirects=True)
                r.encoding = r.apparent_encoding or "utf-8"
                if r.status_code == 200:
                    return r.text
                self._log(f"HTTP 狀態碼異常: {r.status_code} URL: {url}")
            except Exception as e:
                self._log("請求失敗", url, e)
            if attempt + 1 < retries:
                time.sleep(0.5)
        return ""

    def _fetch_json(self, path, referer=None):
        text = self._fetch(path, referer)
        if not text:
            return {}
        try:
            return json.loads(text)
        except Exception as e:
            self._log("JSON 解析異常", e)
            return {}

    def _fix_pic(self, u):
        if not u:
            return ""
        u = str(u).strip().replace("&amp;", "&")
        if u.startswith("data:image"):
            return ""
        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/") and not u.startswith("//"):
            u = self.base_url.rstrip("/") + u
        elif not u.startswith("http://") and not u.startswith("https://"):
            u = self.base_url.rstrip("/") + "/" + u

        if u and not u.endswith(".m3u8") and "@Referer=" not in u:
            u = f"{u}@Referer={self.base_url}/"
        return u

    def _get_img_src(self, el):
        if not el:
            return ""
        img = el if el.name == "img" else el.select_one("img")
        if img:
            for attr in ["data-original", "data-src", "data-echo", "data-bg", "src"]:
                val = img.get(attr, "").strip()
                if val and not val.startswith("data:image"):
                    return self._fix_pic(val)
        style = el.get("style", "") or (img.get("style", "") if img else "")
        if "background" in style:
            m = re.search(r"url\s*\(\s*['\"]?([^'\")]+)['\"]?\s*\)", style, re.I)
            if m and not m.group(1).startswith("data:image"):
                return self._fix_pic(m.group(1))
        return ""

    def init(self, extend=""):
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if ext.get("host"):
                    self.base_url = ext["host"].rstrip("/")
                if "debug" in ext:
                    self.debug = bool(ext["debug"])
            except Exception:
                pass

    def getName(self):
        return "愛迪影視"

    # ----------------------------------------------------------
    # 分類與篩選器
    # ----------------------------------------------------------
    def homeContent(self, filter=False):
        classes = [
            {"type_id": "1", "type_name": "電影"},
            {"type_id": "2", "type_name": "連續劇"},
            {"type_id": "3", "type_name": "綜藝"},
            {"type_id": "4", "type_name": "動漫"}
        ]
        filters = self._build_filters()
        return {"class": classes, "filters": filters}

    def _build_filters(self):
        area = [
            {"n": "全部", "v": ""}, {"n": "大陸", "v": "大陸"}, {"n": "台灣", "v": "台灣"},
            {"n": "香港", "v": "香港"}, {"n": "韓國", "v": "韓國"}, {"n": "日本", "v": "日本"},
            {"n": "美國", "v": "美國"}, {"n": "英國", "v": "英國"}, {"n": "泰國", "v": "泰國"}
        ]
        cur_year = datetime.now().year
        years = [{"n": "全部", "v": ""}] + [{"n": str(y), "v": str(y)} for y in range(cur_year, cur_year - 15, -1)]
        sorts = [
            {"n": "按更新", "v": "time"},
            {"n": "按人氣", "v": "hits"},
            {"n": "按評分", "v": "score"}
        ]

        def get_opt(pairs):
            return [{"n": k, "v": v} for k, v in pairs]

        return {
            "1": [
                {"key": "class", "name": "類型", "value": get_opt([
                    ("全部", ""), ("動作片", "動作片"), ("喜劇片", "喜劇片"), ("愛情片", "愛情片"),
                    ("科幻片", "科幻片"), ("恐怖片", "恐怖片"), ("劇情片", "劇情片"), ("戰爭片", "戰爭片"),
                    ("動畫片", "動畫片"), ("懸疑片", "懸疑片"), ("犯罪片", "犯罪片"), ("奇幻片", "奇幻片")
                ])},
                {"key": "area", "name": "地區", "value": area},
                {"key": "year", "name": "年份", "value": years},
                {"key": "sort", "name": "排序", "value": sorts}
            ],
            "2": [
                {"key": "class", "name": "類型", "value": get_opt([
                    ("全部", ""), ("國產劇", "國產劇"), ("韓劇", "韓劇"), ("台劇", "台劇"),
                    ("日劇", "日劇"), ("歐美劇", "歐美劇"), ("港劇", "港劇"), ("泰劇", "泰劇")
                ])},
                {"key": "area", "name": "地區", "value": area},
                {"key": "year", "name": "年份", "value": years},
                {"key": "sort", "name": "排序", "value": sorts}
            ],
            "3": [
                {"key": "class", "name": "類型", "value": get_opt([
                    ("全部", ""), ("真人秀", "真人秀"), ("搞笑", "搞笑"), ("訪談", "訪談"),
                    ("音樂", "音樂"), ("美食", "美食"), ("旅遊", "旅遊")
                ])},
                {"key": "area", "name": "地區", "value": area},
                {"key": "year", "name": "年份", "value": years},
                {"key": "sort", "name": "排序", "value": sorts}
            ],
            "4": [
                {"key": "class", "name": "類型", "value": get_opt([
                    ("全部", ""), ("熱血", "熱血"), ("戀愛", "戀愛"), ("科幻", "科幻"),
                    ("冒險", "冒險"), ("校園", "校園"), ("搞笑", "搞笑")
                ])},
                {"key": "area", "name": "地區", "value": area},
                {"key": "year", "name": "年份", "value": years},
                {"key": "sort", "name": "排序", "value": sorts}
            ]
        }

    # ----------------------------------------------------------
    # 首頁與分類影片清單
    # ----------------------------------------------------------
    def homeVideoContent(self):
        html = self._fetch("/")
        return {"list": self._parse_items(html)}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg) if pg else 1
        tid = str(tid).strip()

        tid_map = {"movie": "1", "drama": "2", "show": "3", "anime": "4"}
        real_tid = tid_map.get(tid, tid)

        ext = extend if isinstance(extend, dict) else {}
        if isinstance(filter, dict):
            ext.update(filter)

        c_type = ext.get("class", "")
        c_area = ext.get("area", "")
        c_year = ext.get("year", "")
        c_sort = ext.get("sort", "")

        routes = []
        if c_type or c_area or c_year or c_sort:
            routes.append(f"/vodshow/{real_tid}-{c_area}-{c_sort}-{c_type}---{page}---{c_year}.html")
        routes.extend([
            f"/vodshow/{real_tid}--------{page}---.html",
            f"/vodtype/{real_tid}-{page}.html",
            f"/type/{real_tid}-{page}.html",
            f"/{tid}?page={page}"
        ])

        items = []
        for path in routes:
            html = self._fetch(path)
            items = self._parse_items(html)
            if items:
                self._log(f"命中分類路由: {path}, 取得 {len(items)} 筆")
                break

        pagecount = page + 1 if len(items) >= 20 else page
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": len(items) if items else 20,
            "total": pagecount * 20
        }

    def _parse_items(self, html):
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        items, seen = [], set()

        candidates = soup.select(
            ".module-item, .video-item, .public-list-box, .vodlist_item, "
            ".myui-vodlist__box, .stui-vodlist__box, .hl-list-item, li.col-md-2"
        )
        if not candidates:
            candidates = soup.select("a[href*='/detail/'], a[href*='/voddetail/'], a[href*='/video/'], a[href*='/show/']")

        for card in candidates:
            try:
                a = card if card.name == "a" else card.select_one("a[href*='/detail/'], a[href*='/voddetail/'], a[href*='/video/'], a[href*='/show/'], a")
                if not a:
                    continue
                href = a.get("href", "")
                m = re.search(r'/(?:detail|voddetail|video|show)/([0-9A-Za-z_-]+)', href)
                if not m:
                    continue
                vod_id = m.group(1).replace(".html", "")
                if vod_id in seen:
                    continue

                name = a.get("title", "").strip()
                if not name:
                    title_el = card.select_one(".module-item-title, .title, .name, h4, h3, .heading")
                    name = title_el.get_text(strip=True) if title_el else ""
                if not name:
                    img = a.select_one("img")
                    name = img.get("alt", "").strip() if img else ""

                if not name:
                    continue

                seen.add(vod_id)
                pic = self._get_img_src(card) or self._get_img_src(a)
                remark_el = card.select_one(".module-item-note, .pic-text, .remarks, .label, .pic-tag, .tag")
                remarks = remark_el.get_text(strip=True) if remark_el else ""

                items.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })
            except Exception:
                continue
        return items

    # ----------------------------------------------------------
    # 詳情頁解析
    # ----------------------------------------------------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0]).split(",")[0].strip()

        html = ""
        for path in [f"/voddetail/{vid}.html", f"/detail/{vid}.html", f"/video/{vid}.html"]:
            html = self._fetch(path)
            if html and len(html) > 500:
                break

        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")
        name_el = soup.select_one(".module-info-heading h1, .video-info h1, .title, h1, .page-title")
        vod_name = name_el.get_text(strip=True) if name_el else ""

        pic_el = soup.select_one(".module-item-pic, .video-cover, .picture, .lazy, .detail-pic")
        vod_pic = self._get_img_src(pic_el) or self._get_img_src(soup)

        director = actor = ""
        for tag in soup.select(".module-info-item, .info-item, .detail-info-item, .data"):
            txt = tag.get_text(strip=True)
            if "導演" in txt:
                director = txt.split("：")[-1].strip()
            elif "主演" in txt or "演員" in txt:
                actor = txt.split("：")[-1].strip()

        desc_el = soup.select_one(".module-info-introduction-content, .video-desc, .desc, .content, #height_limit")
        vod_content = desc_el.get_text(strip=True) if desc_el else ""

        play_from, play_urls = [], []
        tabs = soup.select(".module-tab-item, .anthology-tab a, .nav-tabs li, .play-source-tab")
        panels = soup.select(".module-list, .anthology-list-box, .tab-content .tab-pane, .playlist, .stui-content__playlist")

        if tabs and panels and len(tabs) <= len(panels):
            for i, tab in enumerate(tabs):
                src_name = tab.get_text(strip=True)
                eps = []
                for a in panels[i].select("a"):
                    ep_title = a.get_text(strip=True)
                    ep_href = a.get("href", "")
                    if ep_title and ep_href:
                        eps.append(f"{ep_title}${ep_href}")
                if eps:
                    play_from.append(src_name)
                    play_urls.append("#".join(eps))
        else:
            all_links = soup.select("a[href*='/vodplay/'], a[href*='/play/']")
            eps = []
            for a in all_links:
                ep_title = a.get_text(strip=True)
                ep_href = a.get("href", "")
                if ep_title and ep_href:
                    eps.append(f"{ep_title}${ep_href}")
            if eps:
                play_from.append("預設播放")
                play_urls.append("#".join(eps))

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_director": director,
                "vod_actor": actor,
                "vod_content": vod_content,
                "vod_play_from": "$$$".join(play_from) if play_from else "預設",
                "vod_play_url": "$$$".join(play_urls) if play_urls else ""
            }]
        }

    # ----------------------------------------------------------
    # 播放解析
    # ----------------------------------------------------------
    def playerContent(self, flag, id, vipFlags=None):
        play_path = str(id).split("$")[-1]

        if play_path.startswith("http") and (".m3u8" in play_path or ".mp4" in play_path):
            return {"parse": 0, "url": play_path, "header": self._headers()}

        play_url = self.base_url.rstrip("/") + "/" + play_path.lstrip("/") if not play_path.startswith("http") else play_path
        html = self._fetch(play_url)
        if not html:
            return {"parse": 1, "url": play_url, "header": self._headers()}

        video_url = ""
        m = re.search(r"player_aaaa\s*=\s*({.*?})<", html, re.S) or re.search(r"player_aaaa\s*=\s*({.*?});", html, re.S)
        if m:
            try:
                p_cfg = json.loads(m.group(1))
                u = p_cfg.get("url", "")
                enc = str(p_cfg.get("encrypt", "0"))
                if enc == "1":
                    u = urllib.parse.unquote(u)
                elif enc == "2":
                    u = urllib.parse.unquote(base64.b64decode(u + "=" * (-len(u) % 4)).decode("utf-8", "ignore"))
                video_url = u
            except Exception:
                pass

        if not video_url:
            m_iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            if m_iframe:
                video_url = m_iframe.group(1)

        if not video_url:
            m_m3u8 = re.search(r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html)
            if m_m3u8:
                video_url = m_m3u8.group(1)

        if video_url:
            if video_url.startswith("//"):
                video_url = "https:" + video_url
            is_m3u8 = ".m3u8" in video_url or ".mp4" in video_url
            return {
                "parse": 0 if is_m3u8 else 1,
                "url": video_url,
                "header": self._headers(referer=self.base_url)
            }

        return {"parse": 1, "url": play_url, "header": self._headers()}

    # ----------------------------------------------------------
    # 搜尋
    # ----------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(str(key).strip())

        # 優先搜尋 suggest JSON 介面
        data = self._fetch_json(f"/index.php/ajax/suggest?mid=1&wd={kw}&limit=50")
        items = []
        if isinstance(data, dict) and data.get("list"):
            for it in data["list"]:
                vid = str(it.get("id") or "")
                if not vid:
                    continue
                items.append({
                    "vod_id": vid,
                    "vod_name": (it.get("name") or "").strip(),
                    "vod_pic": self._fix_pic(it.get("pic", "")),
                    "vod_remarks": (it.get("remarks") or "").strip()
                })
            if items:
                return {"list": items, "page": page, "pagecount": 1, "limit": 50, "total": len(items)}

        # HTML 搜尋路由備援
        search_urls = [
            f"/vodsearch/-------------.html?wd={kw}&page={page}",
            f"/vodsearch/{kw}----------{page}---.html",
            f"/search?wd={kw}&page={page}"
        ]
        for s_url in search_urls:
            html = self._fetch(s_url)
            items = self._parse_items(html)
            if items:
                break

        return {
            "list": items,
            "page": page,
            "pagecount": page if len(items) < 20 else page + 1,
            "limit": 20,
            "total": len(items)
        }

    def localProxy(self, param=''): return {}
    def isVideoFormat(self, url): return False
    def manualVideoCheck(self): return False
    def destroy(self): pass

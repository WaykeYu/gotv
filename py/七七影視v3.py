# -*- coding: utf-8 -*-
"""
七七影視爬蟲外掛 (七七影視.py) - sort-{id}-p{page}.html 分類與篩選適配版
站點: https://www.7749tv.cc/
適用平台: TVBox / CatVod / FongMi
"""
import re
import json
import time
import base64
import urllib.parse

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
    site_url = "https://www.7749tv.cc"
    base_url = "https://www.7749tv.cc"
    debug = False
    timeout = 12

    PLACEHOLDER_KEYS = ("lazy.jpg", "lazy.gif", "loading.gif", "nopic", "default.jpg", "placeholder")

    def __init__(self):
        self.session = requests.Session()
        self._cached_filter_mode = None
        self._cached_detail_tpl = None

    def _log(self, *args):
        if self.debug:
            print("[7749tv]", *args)

    def _web_headers(self, referer=None):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,zh-CN;q=0.8,en;q=0.7",
            "Referer": referer or (self.base_url + "/"),
        }

    def _player_headers(self, referer=None):
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": referer or (self.base_url + "/"),
        }

    def _build_url(self, path):
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"

    def _fetch(self, path, referer=None, retries=2):
        url = self._build_url(path)
        for attempt in range(retries):
            try:
                r = self.session.get(
                    url,
                    headers=self._web_headers(referer),
                    timeout=self.timeout,
                    allow_redirects=True
                )
                if r.status_code == 200:
                    if not r.encoding or r.encoding.lower() in ("iso-8859-1", "ascii"):
                        r.encoding = "utf-8"
                    return r.text
                self._log(f"HTTP {r.status_code}: {url}")
                if r.status_code in (403, 404):
                    break
            except Exception as e:
                self._log("請求失敗:", url, e)
            if attempt + 1 < retries:
                time.sleep(0.4)
        return ""

    def _fetch_json(self, path, referer=None):
        text = self._fetch(path, referer)
        if not text:
            return {}
        try:
            return json.loads(text.lstrip("\ufeff"))
        except Exception as e:
            self._log("JSON 解析異常:", e)
            return {}

    def _is_placeholder(self, url):
        low = url.lower()
        return low.startswith("data:image") or any(k in low for k in self.PLACEHOLDER_KEYS)

    def _fix_pic(self, u):
        if not u:
            return ""
        u = str(u).strip().replace("&amp;", "&")
        if self._is_placeholder(u):
            return ""

        if u.startswith("//"):
            u = "https:" + u
        elif u.startswith("/"):
            u = self.base_url.rstrip("/") + u
        elif not u.startswith(("http://", "https://")):
            u = f"{self.base_url.rstrip('/')}/{u}"

        if u and ".m3u8" not in u and "@Referer=" not in u:
            base_host = urllib.parse.urlparse(self.base_url).netloc
            pic_host = urllib.parse.urlparse(u).netloc
            if base_host and pic_host == base_host:
                u = f"{u}@Referer={self.base_url}/"
        return u

    def _extract_img_from_tag(self, img):
        if not img:
            return ""
        for attr in ("data-original", "data-src", "data-echo", "data-bg", "data-lazy-src", "src"):
            val = (img.get(attr) or "").strip()
            if val and not self._is_placeholder(val):
                fixed = self._fix_pic(val)
                if fixed:
                    return fixed
        return ""

    def _get_img_src(self, el):
        if not el:
            return ""
        if el.name == "img":
            res = self._extract_img_from_tag(el)
            if res:
                return res

        for img in el.select("img.lazy, img"):
            res = self._extract_img_from_tag(img)
            if res:
                return res

        targets = [el] + el.select("[style*='background']")
        for target in targets:
            style = target.get("style") or ""
            if "background" in style:
                m = re.search(r"url\s*\(\s*['\"]?([^'\")]+)['\"]?\s*\)", style, re.I)
                if m and not self._is_placeholder(m.group(1)):
                    fixed = self._fix_pic(m.group(1))
                    if fixed:
                        return fixed
        return ""

    @staticmethod
    def _clean_tvbox_str(s):
        return re.sub(r'[$#\r\n\t]+', ' ', str(s)).strip()

    def init(self, extend=""):
        if extend:
            try:
                ext = json.loads(extend) if isinstance(extend, str) else extend
                if isinstance(ext, dict):
                    if ext.get("host"):
                        self.base_url = ext["host"].rstrip("/")
                    if "debug" in ext:
                        self.debug = bool(ext["debug"])
            except Exception as e:
                self._log("init extend 解析失敗:", e)

    def getName(self):
        return "七七影視"

    # ----------------------------------------------------------
    # 首頁與分類篩選器 (對應 /sort-{tid}-p{pg}.html)
    # ----------------------------------------------------------
    def homeContent(self, filter=False):
        classes = [
            {"type_id": "1", "type_name": "電影"},
            {"type_id": "2", "type_name": "連續劇"},
            {"type_id": "3", "type_name": "綜藝"},
            {"type_id": "4", "type_name": "動漫"},
        ]

        # 通用篩選選項
        area_opts = [
            {"n": "全部", "v": ""},
            {"n": "大陸", "v": "大陸"},
            {"n": "香港", "v": "香港"},
            {"n": "台灣", "v": "台灣"},
            {"n": "美國", "v": "美國"},
            {"n": "韓國", "v": "韓國"},
            {"n": "日本", "v": "日本"},
            {"n": "泰國", "v": "泰國"},
            {"n": "英國", "v": "英國"},
            {"n": "其他", "v": "其他"},
        ]
        year_opts = [{"n": "全部", "v": ""}] + [
            {"n": str(y), "v": str(y)} for y in range(2026, 2014, -1)
        ] + [{"n": "更早", "v": "更早"}]

        sort_opts = [
            {"n": "按時間", "v": "time"},
            {"n": "按人氣", "v": "hit"},
            {"n": "按評分", "v": "score"},
        ]

        movie_types = [
            {"n": "全部", "v": ""},
            {"n": "動作片", "v": "動作"},
            {"n": "喜劇片", "v": "喜劇"},
            {"n": "愛情片", "v": "愛情"},
            {"n": "科幻片", "v": "科幻"},
            {"n": "恐怖片", "v": "恐怖"},
            {"n": "劇情片", "v": "劇情"},
            {"n": "戰爭片", "v": "戰爭"},
            {"n": "犯罪片", "v": "犯罪"},
            {"n": "紀錄片", "v": "紀錄"},
        ]
        drama_types = [
            {"n": "全部", "v": ""},
            {"n": "國產劇", "v": "國產"},
            {"n": "港台劇", "v": "港台"},
            {"n": "日韓劇", "v": "日韓"},
            {"n": "歐美劇", "v": "歐美"},
            {"n": "泰劇", "v": "泰劇"},
            {"n": "古裝", "v": "古裝"},
            {"n": "懸疑", "v": "懸疑"},
            {"n": "都市", "v": "都市"},
        ]
        variety_types = [
            {"n": "全部", "v": ""},
            {"n": "真人秀", "v": "真人秀"},
            {"n": "脫口秀", "v": "脫口秀"},
            {"n": "選秀", "v": "選秀"},
            {"n": "音樂", "v": "音樂"},
            {"n": "訪談", "v": "訪談"},
        ]
        anime_types = [
            {"n": "全部", "v": ""},
            {"n": "熱血", "v": "熱血"},
            {"n": "戀愛", "v": "戀愛"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "冒險", "v": "冒險"},
            {"n": "校園", "v": "校園"},
            {"n": "機戰", "v": "機戰"},
        ]

        def build_filter_group(type_list):
            return [
                {"key": "class", "name": "類型", "value": type_list},
                {"key": "area", "name": "地區", "value": area_opts},
                {"key": "year", "name": "年份", "value": year_opts},
                {"key": "by", "name": "排序", "value": sort_opts},
            ]

        filters = {
            "1": build_filter_group(movie_types),
            "2": build_filter_group(drama_types),
            "3": build_filter_group(variety_types),
            "4": build_filter_group(anime_types),
        }

        return {"class": classes, "filters": filters}

    def homeVideoContent(self):
        html = self._fetch("/")
        return {"list": self._parse_items(html)}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg) if pg else 1
        tid = str(tid).strip()

        # 兼容外部傳入拼音或數字
        reverse_alias = {
            "dianying": "1", "movie": "1",
            "dianshiju": "2", "drama": "2",
            "zongyi": "3", "show": "3",
            "dongman": "4", "anime": "4",
        }
        tid = reverse_alias.get(tid, tid)

        # 解析篩選條件
        ext = {}
        if extend:
            if isinstance(extend, str):
                try:
                    ext = json.loads(extend)
                except Exception:
                    ext = {}
            elif isinstance(extend, dict):
                ext = extend

        f_class = (ext.get("class") or "").strip()
        f_area = (ext.get("area") or "").strip()
        f_year = (ext.get("year") or "").strip()
        f_by = (ext.get("by") or "").strip()

        has_filter = any([f_class, f_area, f_year, f_by])
        items = []

        if not has_filter:
            # 基準路由：https://www.7749tv.cc/sort-1-p1.html
            routes = [
                f"/sort-{tid}-p{page}.html",
                f"/sort-{tid}-{page}.html",
            ]
            for path in routes:
                html = self._fetch(path)
                items = self._parse_items(html)
                if items:
                    self._log(f"命中分類路由: {path}, 取得 {len(items)} 筆")
                    break
        else:
            q_class = urllib.parse.quote(f_class)
            q_area = urllib.parse.quote(f_area)
            q_year = urllib.parse.quote(f_year)
            q_by = urllib.parse.quote(f_by)

            # 海洋CMS / 自定義 sort 篩選常見偽靜態與動態路由
            filter_candidates = [
                # 模式 1: SeaCMS 偽靜態篩選
                ("seacms_rewrite", f"/search.php?searchtype=5&tid={tid}&jq={q_class}&area={q_area}&year={q_year}&order={q_by}&page={page}"),
                # 模式 2: sort 多段式偽靜態 (/sort-{tid}-{class}-{area}-{year}--{by}-p{page}.html)
                ("sort_multi", f"/sort-{tid}-{q_class}-{q_area}-{q_year}--{q_by}-p{page}.html"),
                # 模式 3: sort 附帶 Query 參數
                ("sort_query", f"/sort-{tid}-p{page}.html?class={q_class}&area={q_area}&year={q_year}&by={q_by}"),
                # 模式 4: 蘋果CMS vodshow 備援
                ("vodshow", f"/vodshow/{tid}-{q_area}-{q_by}-{q_class}-----{page}---{q_year}.html"),
            ]

            if self._cached_filter_mode:
                filter_candidates.sort(key=lambda x: 0 if x[0] == self._cached_filter_mode else 1)

            for mode, path in filter_candidates:
                html = self._fetch(path)
                items = self._parse_items(html)
                if items:
                    self._cached_filter_mode = mode
                    self._log(f"命中篩選路由 [{mode}]: {path}, 取得 {len(items)} 筆")
                    break

            # 若篩選路由無結果，自動降級回基本分類頁避免空白
            if not items:
                html = self._fetch(f"/sort-{tid}-p{page}.html")
                items = self._parse_items(html)

        pagecount = page + 1 if len(items) >= 18 else page
        return {
            "list": items,
            "page": page,
            "pagecount": pagecount,
            "limit": len(items) if items else 20,
            "total": pagecount * 20,
        }

    def _parse_items(self, html):
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        items, seen = [], set()

        candidates = soup.select(
            ".module-item, .video-item, .public-list-box, .vodlist_item, "
            ".myui-vodlist__box, .stui-vodlist__box, .stui-vodlist__item, "
            ".fed-list-item, .hl-list-item, .pack-ykpack, li.col-md-2, li.col-sm-3, li.col-xs-4"
        )

        if not candidates:
            candidates = soup.select(
                "a[href*='/detail/'], a[href*='/voddetail/'], a[href*='/video/'], a[href*='/vodplay/'], a[href*='/view/'], a[href*='/movie/']"
            )

        for card in candidates:
            try:
                a = card if card.name == "a" else card.select_one(
                    "a[href*='/detail/'], a[href*='/voddetail/'], a[href*='/video/'], a[href*='/vodplay/'], a[href*='/view/'], a[href*='/movie/'], a"
                )
                if not a:
                    continue
                href = a.get("href") or ""
                # 排除分類連結 (/sort-1-p1.html) 避免誤抓導覽列
                if "/sort-" in href or "/vodtype/" in href:
                    continue

                m = re.search(r"/(?:detail|voddetail|video|show|vodplay|view|movie)/([0-9A-Za-z_-]+)", href)
                if not m:
                    # 兼容 /12345.html 或 /id-12345.html 格式
                    m = re.search(r"/(?:id-)?(\d+)(?:-\d+-\d+)?\.html$", href)
                if not m:
                    continue

                vod_id = m.group(1).replace(".html", "").split("-")[0]
                if not vod_id or vod_id in seen:
                    continue

                name = (a.get("title") or "").strip()
                if not name:
                    title_el = card.select_one(".module-item-title, .stui-vodlist__title, .myui-vodlist__title, .title, .name, h4, h3, .heading")
                    name = title_el.get_text(strip=True) if title_el else ""
                if not name:
                    img = card.select_one("img") or a.select_one("img")
                    name = (img.get("alt") or "").strip() if img else ""
                name = re.sub(r"封[面麵]$", "", name).strip()
                if not name:
                    continue

                pic = self._get_img_src(card)
                if not pic and card is not a:
                    pic = self._get_img_src(a)
                if not pic and card.parent:
                    pic = self._get_img_src(card.parent)

                seen.add(vod_id)
                remark_el = card.select_one(".module-item-note, .pic-text, .remarks, .label, .pic-tag, .tag, .text-right")
                remarks = remark_el.get_text(strip=True) if remark_el else ""

                items.append({
                    "vod_id": vod_id,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remarks,
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

        detail_tpls = [
            "/voddetail/{vid}.html",
            "/detail/{vid}.html",
            "/video/{vid}.html",
            "/view/{vid}.html",
            "/movie/{vid}.html",
            "/{vid}.html",
        ]
        if self._cached_detail_tpl in detail_tpls:
            detail_tpls.remove(self._cached_detail_tpl)
            detail_tpls.insert(0, self._cached_detail_tpl)

        html = ""
        for tpl in detail_tpls:
            html = self._fetch(tpl.format(vid=vid))
            if html and len(html) > 500:
                self._cached_detail_tpl = tpl
                break

        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")
        name_el = soup.select_one(".module-info-heading h1, .stui-content__detail .title, .myui-content__detail .title, .video-info h1, h1, .page-title")
        vod_name = name_el.get_text(strip=True) if name_el else ""

        pic_el = soup.select_one(".module-item-pic, .stui-content__thumb, .myui-content__thumb, .video-cover, .picture, .detail-pic, img.lazy")
        vod_pic = self._get_img_src(pic_el) or self._get_img_src(soup)

        director = actor = ""
        for tag in soup.select(".module-info-item, .info-item, .detail-info-item, .data, p"):
            txt = tag.get_text(" ", strip=True)
            if re.search(r"導\s*演|导\s*演", txt) and len(txt) < 120:
                director = re.split(r"[:：]", txt, maxsplit=1)[-1].strip()
            elif re.search(r"主\s*演|演\s*員|演\s*员", txt) and len(txt) < 300:
                actor = re.split(r"[:：]", txt, maxsplit=1)[-1].strip()

        desc_el = soup.select_one(".module-info-introduction-content, .stui-content__desc, .myui-content__desc, .video-desc, .desc, .content, #height_limit")
        vod_content = desc_el.get_text(strip=True) if desc_el else ""

        play_from, play_urls = [], []
        tabs = soup.select(".module-tab-item, .anthology-tab a, .nav-tabs li, .play-source-tab, .stui-pannel__head h3")
        panels = soup.select(".module-list, .anthology-list-box, .tab-content .tab-pane, .playlist, .stui-content__playlist, .myui-content__list")

        if tabs and panels and len(tabs) <= len(panels):
            for i, tab in enumerate(tabs):
                src_name = self._clean_tvbox_str(tab.get_text(strip=True)) or f"線路{i + 1}"
                eps, seen_hrefs = [], set()
                for a in panels[i].select("a"):
                    ep_title = self._clean_tvbox_str(a.get_text(strip=True))
                    ep_href = (a.get("href") or "").strip()
                    if ep_title and ep_href and ep_href not in seen_hrefs and not ep_href.startswith("javascript"):
                        seen_hrefs.add(ep_href)
                        eps.append(f"{ep_title}${ep_href}")
                if eps:
                    play_from.append(src_name)
                    play_urls.append("#".join(eps))
        else:
            eps, seen_hrefs = [], set()
            for a in soup.select("a[href*='/vodplay/'], a[href*='/play/'], a[href*='/video/']"):
                ep_title = self._clean_tvbox_str(a.get_text(strip=True))
                ep_href = (a.get("href") or "").strip()
                if not ep_title or not ep_href or ep_href in seen_hrefs:
                    continue
                if any(k in ep_title for k in ("立即播放", "在線觀看", "在线观看")):
                    continue
                seen_hrefs.add(ep_href)
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
                "vod_play_url": "$$$".join(play_urls) if play_urls else "",
            }]
        }

    # ----------------------------------------------------------
    # 播放解析
    # ----------------------------------------------------------
    @staticmethod
    def _decode_player_url(raw_url, encrypt_flag):
        u = str(raw_url).strip()
        enc = str(encrypt_flag or "0").strip()
        try:
            if enc == "1":
                u = urllib.parse.unquote(u)
            elif enc == "2":
                padded = u + "=" * (-len(u) % 4)
                u = urllib.parse.unquote(base64.b64decode(padded).decode("utf-8", "ignore"))
        except Exception:
            pass
        return u

    def playerContent(self, flag, id, vipFlags=None):
        play_path = str(id).split("$")[-1].strip()
        hdr = self._player_headers(referer=self.base_url + "/")

        if play_path.startswith("http") and re.search(r"\.(?:m3u8|mp4|flv)(?:\?|$)", play_path, re.I):
            return {"parse": 0, "url": play_path, "header": hdr}

        play_url = self._build_url(play_path)
        html = self._fetch(play_url)
        if not html:
            return {"parse": 1, "url": play_url, "header": hdr}

        video_url = ""
        m = re.search(r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*(?:;|</script>)", html, re.S) or \
            re.search(r"player_aaaa\s*=\s*(\{.*?\})\s*(?:;|</script>)", html, re.S)
        if m:
            try:
                p_cfg = json.loads(m.group(1))
                video_url = self._decode_player_url(p_cfg.get("url", ""), p_cfg.get("encrypt", "0"))
            except Exception as e:
                self._log("player_aaaa JSON 解析失敗:", e)

        if not video_url:
            m_iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            if m_iframe:
                video_url = m_iframe.group(1).strip()

        if not video_url:
            m_m3u8 = re.search(r'(https?://[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)', html, re.I)
            if m_m3u8:
                video_url = m_m3u8.group(1).strip()

        if video_url:
            if video_url.startswith("//"):
                video_url = "https:" + video_url
            is_direct = bool(re.search(r"\.(?:m3u8|mp4|flv)(?:\?|$)", video_url, re.I))
            return {
                "parse": 0 if is_direct else 1,
                "url": video_url,
                "header": hdr,
            }

        return {"parse": 1, "url": play_url, "header": hdr}

    # ----------------------------------------------------------
    # 搜尋介面
    # ----------------------------------------------------------
    def searchContent(self, key, quick, pg="1"):
        page = int(pg) if pg else 1
        kw = urllib.parse.quote(str(key).strip())

        if page == 1:
            data = self._fetch_json(f"/index.php/ajax/suggest?mid=1&wd={kw}&limit=50")
            items = []
            if isinstance(data, dict) and data.get("list"):
                for it in data["list"]:
                    vid = str(it.get("id") or "").strip()
                    if not vid:
                        continue
                    items.append({
                        "vod_id": vid,
                        "vod_name": (it.get("name") or "").strip(),
                        "vod_pic": self._fix_pic(it.get("pic", "")),
                        "vod_remarks": (it.get("remarks") or "").strip(),
                    })
                if items:
                    return {"list": items, "page": 1, "pagecount": 1, "limit": len(items), "total": len(items)}

        search_urls = [
            f"/search.php?page={page}&searchword={kw}&searchtype=",
            f"/vodsearch/-------------.html?wd={kw}&page={page}",
            f"/vodsearch/{kw}----------{page}---.html",
            f"/search?wd={kw}&page={page}",
        ]
        items = []
        for s_url in search_urls:
            html = self._fetch(s_url)
            items = self._parse_items(html)
            if items:
                break

        return {
            "list": items,
            "page": page,
            "pagecount": page if len(items) < 18 else page + 1,
            "limit": 20,
            "total": len(items),
        }

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

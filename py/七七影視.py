# -*- coding: utf-8 -*-
"""
七七影視爬蟲外掛 (七七影視.py) - Yumilo Windows 動態代理與完整播放修復版
站點: https://www.7749tv.cc/
適用平台: Yumilo Windows / TVBox / CatVod / FongMi / box_py
"""
import re
import json
import time
import base64
import urllib.parse
import urllib3

import requests
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
        def getProxyUrl(self, local=True): return ""
        def destroy(self): pass


class Spider(BaseSpider):
    site_url = "https://www.7749tv.cc"
    base_url = "https://www.7749tv.cc"
    debug = False
    timeout = 12
    use_stream_proxy = True
    use_pic_proxy = False

    PLACEHOLDER_KEYS = ("lazy.jpg", "lazy.gif", "loading.gif", "nopic", "default.jpg", "placeholder")
    EXCLUDE_HREF_KEYS = (
        "/sort-", "/vodtype/", "/vodshow/", "/search", "/topic", "/actor",
        "/director", "/gbook", "/user", "/label", "/rss", "/map", "javascript:", "#"
    )

    T2S_MAP = str.maketrans({
        "陸": "陆", "台": "台", "灣": "湾", "國": "国", "韓": "韩", "歐": "欧",
        "動": "动", "劇": "剧", "喜": "喜", "愛": "爱", "恐": "恐", "戰": "战",
        "紀": "纪", "錄": "录", "裝": "装", "懸": "悬", "脫": "脱", "選": "选",
        "音": "音", "樂": "乐", "訪": "访", "談": "谈", "熱": "热", "戀": "恋",
        "冒": "冒", "險": "险", "園": "园", "機": "机", "綜": "综", "藝": "艺",
        "漫": "漫", "電": "电", "影": "影", "連": "连", "續": "续", "更": "更"
    })

    def __init__(self):
        self.session = requests.Session()
        self._cached_filter_tpl = None
        self._cached_detail_tpl = "/info-{vid}.html"
        self._id_href_map = {}

    def _log(self, *args):
        if self.debug:
            print("[7749tv]", *args)

    def _to_simplified(self, text):
        return str(text).translate(self.T2S_MAP)

    def _proxy_base(self):
        """動態取得 Yumilo / TVBox 實際分配的本地代理網址，避免埠號寫死導致連線失敗"""
        for call in (lambda: self.getProxyUrl(True), lambda: self.getProxyUrl()):
            try:
                u = call()
                if u and isinstance(u, str) and u.startswith("http"):
                    return u
            except Exception:
                pass
        return ""

    def _build_proxy_url(self, media_type, target_url):
        base = self._proxy_base()
        if not base:
            # 若執行環境未提供代理埠號，直接回傳原始網址避免連到無效的 127.0.0.1:9978
            return target_url
        b64 = base64.urlsafe_b64encode(target_url.encode("utf-8")).decode("ascii")
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}type={media_type}&url={b64}"

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
                    allow_redirects=True,
                    verify=False,
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

        if u.startswith("http://"):
            if self.use_pic_proxy and self._proxy_base():
                return self._build_proxy_url("pic", u)
            u = "https://" + u[7:]

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
            return self._extract_img_from_tag(el)

        for img in el.select("img"):
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

    @classmethod
    def _extract_vod_id(cls, href):
        if not href:
            return ""
        low = href.lower().strip()
        if any(k in low for k in cls.EXCLUDE_HREF_KEYS):
            return ""

        path = urllib.parse.urlparse(href).path

        m = re.search(r"/(?:info|view|movie|vod|detail|video|play|vodplay)-([0-9A-Za-z_]+?)(?:-\d+-\d+)?\.html$", path, re.I)
        if m:
            return m.group(1)

        m = re.search(r"/(?:detail|voddetail|video|show|vodplay|view|movie|info|vod)/([0-9A-Za-z_]+)(?:-\d+-\d+)?(?:\.html)?$", path, re.I)
        if m:
            return m.group(1)

        m = re.search(r"^/(\d+)\.html$", path)
        if m:
            return m.group(1)

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
                    if "pic_proxy" in ext:
                        self.use_pic_proxy = bool(ext["pic_proxy"])
                    if "stream_proxy" in ext:
                        self.use_stream_proxy = bool(ext["stream_proxy"])
            except Exception as e:
                self._log("init extend 解析失敗:", e)

    def getName(self):
        return "七七影視"

    # ----------------------------------------------------------
    # 首頁與分類篩選器
    # ----------------------------------------------------------
    def homeContent(self, filter=False):
        classes = [
            {"type_id": "1", "type_name": "電影"},
            {"type_id": "2", "type_name": "連續劇"},
            {"type_id": "3", "type_name": "綜藝"},
            {"type_id": "4", "type_name": "動漫"},
        ]

        area_opts = [
            {"n": "全部", "v": ""},
            {"n": "大陸", "v": "大陆"},
            {"n": "香港", "v": "香港"},
            {"n": "台灣", "v": "台湾"},
            {"n": "美國", "v": "美国"},
            {"n": "韓國", "v": "韩国"},
            {"n": "日本", "v": "日本"},
            {"n": "泰國", "v": "泰国"},
            {"n": "英國", "v": "英国"},
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
            {"n": "動作片", "v": "动作"},
            {"n": "喜劇片", "v": "喜剧"},
            {"n": "愛情片", "v": "爱情"},
            {"n": "科幻片", "v": "科幻"},
            {"n": "恐怖片", "v": "恐怖"},
            {"n": "劇情片", "v": "剧情"},
            {"n": "戰爭片", "v": "战争"},
            {"n": "犯罪片", "v": "犯罪"},
            {"n": "紀錄片", "v": "纪录"},
        ]
        drama_types = [
            {"n": "全部", "v": ""},
            {"n": "國產劇", "v": "国产"},
            {"n": "港台劇", "v": "港台"},
            {"n": "日韓劇", "v": "日韩"},
            {"n": "歐美劇", "v": "欧美"},
            {"n": "泰劇", "v": "泰剧"},
            {"n": "古裝", "v": "古装"},
            {"n": "懸疑", "v": "悬疑"},
            {"n": "都市", "v": "都市"},
        ]
        variety_types = [
            {"n": "全部", "v": ""},
            {"n": "真人秀", "v": "真人秀"},
            {"n": "脫口秀", "v": "脱口秀"},
            {"n": "選秀", "v": "选秀"},
            {"n": "音樂", "v": "音乐"},
            {"n": "訪談", "v": "访谈"},
        ]
        anime_types = [
            {"n": "全部", "v": ""},
            {"n": "熱血", "v": "热血"},
            {"n": "戀愛", "v": "恋爱"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "冒險", "v": "冒险"},
            {"n": "校園", "v": "校园"},
            {"n": "機戰", "v": "机战"},
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

        html = self._fetch("/")
        home_list = self._parse_items(html)
        return {"class": classes, "filters": filters, "list": home_list}

    def homeVideoContent(self):
        html = self._fetch("/")
        return {"list": self._parse_items(html)}

    def categoryContent(self, tid, pg, filter=False, extend=None):
        page = int(pg) if pg else 1
        tid = str(tid).strip()

        reverse_alias = {
            "dianying": "1", "movie": "1",
            "dianshiju": "2", "drama": "2",
            "zongyi": "3", "show": "3",
            "dongman": "4", "anime": "4",
        }
        tid = reverse_alias.get(tid, tid)

        ext = {}
        if extend:
            if isinstance(extend, str):
                try:
                    ext = json.loads(extend)
                except Exception:
                    ext = dict(urllib.parse.parse_qsl(extend))
            elif isinstance(extend, dict):
                ext = extend

        f_class = self._to_simplified((ext.get("class") or "").strip())
        f_area = self._to_simplified((ext.get("area") or "").strip())
        f_year = (ext.get("year") or "").strip()
        f_by = (ext.get("by") or "").strip()

        has_filter = any([f_class, f_area, f_year, f_by])
        items = []

        if not has_filter:
            for path in (f"/sort-{tid}-p{page}.html", f"/sort-{tid}-{page}.html"):
                html = self._fetch(path)
                items = self._parse_items(html)
                if items:
                    break
        else:
            q_class = urllib.parse.quote(f_class)
            q_area = urllib.parse.quote(f_area)
            q_year = urllib.parse.quote(f_year)
            q_by = urllib.parse.quote(f_by)

            filter_routes = [
                f"/search.php?searchtype=5&tid={tid}&jq={q_class}&area={q_area}&year={q_year}&order={q_by}&page={page}",
                f"/sort-{tid}-{q_class}-{q_area}-{q_year}--{q_by}-p{page}.html",
                f"/sort-{tid}-{q_class}-{q_area}-{q_year}---{q_by}-p{page}.html",
                f"/vodshow/{tid}-{q_area}-{q_by}-{q_class}-----{page}---{q_year}.html",
            ]

            for path in filter_routes:
                html = self._fetch(path)
                items = self._parse_items(html)
                if items:
                    break

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

        for a in soup.select("a[href]"):
            try:
                href = (a.get("href") or "").strip()
                vod_id = self._extract_vod_id(href)
                if not vod_id or vod_id in seen:
                    continue

                name = ""
                pname_el = a.select_one("p.pname, .pname")
                if pname_el:
                    name = pname_el.get_text(strip=True)

                if not name:
                    name = (a.get("title") or "").strip()

                if not name:
                    img = a.select_one("img")
                    if img:
                        name = re.sub(r"(?:海報|海报|封[面麵])$", "", (img.get("alt") or "")).strip()

                if not name:
                    for sel in (".module-item-title", ".stui-vodlist__title", ".myui-vodlist__title", "h4", "h3", ".name"):
                        el = a.select_one(sel)
                        if el and el.get_text(strip=True):
                            name = el.get_text(strip=True)
                            break

                if not name and a.parent and a.parent.name == "li":
                    p_alt = a.parent.select_one("p.pname, .pname, h4, h3, a[title]")
                    if p_alt:
                        name = (p_alt.get("title") or p_alt.get_text(strip=True) or "").strip()

                name = re.sub(r"(?:海報|海报|封[面麵])$", "", name).strip()
                if not name:
                    continue

                pic = self._get_img_src(a)
                if not pic and a.parent and a.parent.name == "li":
                    pic = self._get_img_src(a.parent)

                remarks = ""
                lbl = a.select_one("label.title, .module-item-note, .pic-text, .remarks, .label, .pic-tag")
                if lbl:
                    lbl_txt = lbl.get_text(strip=True)
                    if lbl_txt:
                        remarks = lbl_txt
                if not remarks:
                    starring = a.select_one("p.pstarring, .pstarring")
                    if starring:
                        remarks = starring.get_text(strip=True)

                seen.add(vod_id)
                if "play" not in href.lower():
                    self._id_href_map[vod_id] = href

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
    # 詳情頁解析 (/info-{vid}.html)
    # ----------------------------------------------------------
    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        vid = str(ids[0]).split(",")[0].strip()

        detail_tpls = [
            "/info-{vid}.html",
            "/view-{vid}.html",
            "/movie-{vid}.html",
            "/voddetail/{vid}.html",
            "/detail/{vid}.html",
            "/{vid}.html",
        ]
        if self._cached_detail_tpl in detail_tpls:
            detail_tpls.remove(self._cached_detail_tpl)
            detail_tpls.insert(0, self._cached_detail_tpl)

        candidate_paths = [tpl.format(vid=vid) for tpl in detail_tpls]
        if vid in self._id_href_map:
            candidate_paths.insert(0, self._id_href_map[vid])

        html = ""
        for path in dict.fromkeys(candidate_paths):
            html = self._fetch(path)
            if html and len(html) > 500:
                if "{vid}" not in path and vid in path:
                    self._cached_detail_tpl = path.replace(vid, "{vid}")
                break

        if not html:
            return {"list": []}

        soup = BeautifulSoup(html, "html.parser")
        name_el = soup.select_one(".module-info-heading h1, .stui-content__detail .title, .myui-content__detail .title, .video-info h1, h1, .page-title")
        vod_name = name_el.get_text(strip=True) if name_el else ""

        pic_el = soup.select_one(".psize img, .module-item-pic, .stui-content__thumb, .myui-content__thumb, .video-cover, .picture, .detail-pic, img")
        vod_pic = self._get_img_src(pic_el) or self._get_img_src(soup)

        director = actor = ""
        for tag in soup.select(".module-info-item, .info-item, .detail-info-item, .data, p, li"):
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
            # 依播放線路分組收集所有分集連結（例如 /play-55067-0-1.html 的中間段代表線路索引）
            grouped = {}
            for a in soup.select("a[href*='/play-'], a[href*='/vodplay/'], a[href*='/play/'], a[href*='/video-'], a[href*='/video/']"):
                ep_title = self._clean_tvbox_str(a.get_text(strip=True))
                ep_href = (a.get("href") or "").strip()
                if not ep_title or not ep_href or ep_href.startswith("javascript"):
                    continue
                if any(k in ep_title for k in ("立即播放", "在線觀看", "在线观看", "倒序", "正序")):
                    continue

                m_line = re.search(r"/(?:play|vodplay)[-/]\d+[-/](\d+)[-/]\d+", ep_href)
                line_key = f"線路{int(m_line.group(1)) + 1}" if m_line else "預設播放"
                grouped.setdefault(line_key, [])
                entry = f"{ep_title}${ep_href}"
                if entry not in grouped[line_key]:
                    grouped[line_key].append(entry)

            for line_name, eps in grouped.items():
                if eps:
                    play_from.append(line_name)
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
    # 播放解析與動態代理（解決 Yumilo Windows SSL 憑證失敗與連續劇變數）
    # ----------------------------------------------------------
    @staticmethod
    def _decode_player_url(raw_url, encrypt_flag="0"):
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

    @staticmethod
    def _unwrap_stream_url(target_url):
        if not target_url:
            return ""
        u = target_url.strip().replace("&amp;", "&")
        if u.startswith("//"):
            u = "https:" + u

        try:
            parsed = urllib.parse.urlparse(u)
            qs = urllib.parse.parse_qs(parsed.query)
            for key in ("url", "v", "vid", "src", "link", "play"):
                if key in qs and qs[key]:
                    inner = urllib.parse.unquote(qs[key][0]).strip()
                    if inner.startswith("//"):
                        inner = "https:" + inner
                    if inner.startswith(("http://", "https://")):
                        return inner
        except Exception:
            pass
        return u

    def _wrap_stream_proxy(self, stream_url):
        if not self.use_stream_proxy:
            return stream_url
        return self._build_proxy_url("m3u8", stream_url)

    def playerContent(self, flag, id, vipFlags=None):
        play_path = str(id).split("$")[-1].strip()
        hdr = self._player_headers(referer=self.base_url + "/")

        unwrapped_init = self._unwrap_stream_url(play_path)
        if unwrapped_init.startswith(("http://", "https://")) and re.search(r"\.(?:m3u8|mp4|flv)(?:\?|$)", unwrapped_init, re.I):
            is_m3u8 = ".m3u8" in unwrapped_init.lower()
            out_url = self._wrap_stream_proxy(unwrapped_init) if is_m3u8 else unwrapped_init
            return {"parse": 0, "url": out_url, "header": {} if out_url != unwrapped_init else hdr}

        play_url = self._build_url(play_path)
        html = self._fetch(play_url)
        if not html:
            return {"parse": 1, "url": play_url, "header": hdr}

        video_url = ""

        # 1. 海洋CMS 常見變數: var now="https://..."; 或 var now=unescape("...");
        m_now = re.search(r'\bvar\s+now\s*=\s*(?:unescape\s*\(\s*)?["\']([^"\']+)["\']', html)
        if m_now:
            video_url = urllib.parse.unquote(m_now.group(1).strip())

        # 2. 蘋果CMS 變數: player_aaaa = {...}
        if not video_url:
            m = re.search(r"var\s+player_aaaa\s*=\s*(\{.*?\})\s*(?:;|</script>)", html, re.S) or \
                re.search(r"player_aaaa\s*=\s*(\{.*?\})\s*(?:;|</script>)", html, re.S)
            if m:
                try:
                    p_cfg = json.loads(m.group(1))
                    video_url = self._decode_player_url(p_cfg.get("url", ""), p_cfg.get("encrypt", "0"))
                except Exception as e:
                    self._log("player_aaaa JSON 解析失敗:", e)

        # 3. iframe src 提取（如 https://api.taiju.bid/2020/?url=https://.../index.m3u8）
        if not video_url:
            m_iframe = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            if m_iframe:
                video_url = m_iframe.group(1).strip()

        # 4. 全域匹配 .m3u8 / .mp4 直鏈
        if not video_url:
            clean_html = html.replace(r"\/", "/")
            m_m3u8 = re.search(r'(https?://[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)', clean_html, re.I)
            if m_m3u8:
                video_url = m_m3u8.group(1).strip()

        if video_url:
            final_url = self._unwrap_stream_url(video_url)
            is_m3u8 = bool(re.search(r"\.m3u8(?:\?|$)", final_url, re.I))
            is_direct = bool(re.search(r"\.(?:m3u8|mp4|flv)(?:\?|$)", final_url, re.I))

            if is_m3u8 and self.use_stream_proxy:
                proxied = self._wrap_stream_proxy(final_url)
                return {
                    "parse": 0,
                    "url": proxied,
                    "header": {} if proxied != final_url else hdr,
                }
            return {
                "parse": 0 if is_direct else 1,
                "url": final_url,
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

    # ----------------------------------------------------------
    # 本地代理（動態適配 Yumilo Windows 代理埠號）
    # ----------------------------------------------------------
    def localProxy(self, param=''):
        try:
            params = param if isinstance(param, dict) else json.loads(param)
            ptype = params.get("type", "")
            b64_url = params.get("url", "")
            if not b64_url:
                return [404, "text/plain", b""]

            padded = b64_url + "=" * (-len(b64_url) % 4)
            raw_url = base64.urlsafe_b64decode(padded).decode("utf-8")

            if ptype == "pic":
                r = self.session.get(raw_url, headers=self._player_headers(), timeout=10, verify=False)
                if r.status_code == 200:
                    return [200, r.headers.get("Content-Type", "image/jpeg"), r.content]

            elif ptype == "m3u8":
                r = self.session.get(raw_url, headers=self._player_headers(), timeout=12, verify=False)
                if r.status_code != 200:
                    return [r.status_code, "text/plain", b""]

                r.encoding = "utf-8"
                final_base = r.url
                lines = []
                for line in r.text.splitlines():
                    s = line.strip()
                    if not s:
                        lines.append(line)
                        continue
                    if s.startswith("#"):
                        if 'URI="' in s:
                            def _repl_uri(m):
                                abs_u = urllib.parse.urljoin(final_base, m.group(1))
                                return f'URI="{self._build_proxy_url("ts", abs_u)}"'
                            s = re.sub(r'URI="([^"]+)"', _repl_uri, s)
                        lines.append(s)
                    else:
                        abs_u = urllib.parse.urljoin(final_base, s)
                        sub_type = "m3u8" if ".m3u8" in abs_u.lower() else "ts"
                        lines.append(self._build_proxy_url(sub_type, abs_u))

                content = "\n".join(lines).encode("utf-8")
                return [200, "application/vnd.apple.mpegurl", content]

            elif ptype == "ts":
                r = self.session.get(raw_url, headers=self._player_headers(), timeout=15, verify=False)
                if r.status_code == 200:
                    ctype = r.headers.get("Content-Type", "video/mp2t")
                    return [200, ctype, r.content]

        except Exception as e:
            self._log("localProxy 異常:", e)
        return [404, "text/plain", b""]

    def destroy(self):
        try:
            self.session.close()
        except Exception:
            pass

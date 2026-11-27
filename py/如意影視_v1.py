import re
import os
import json
import time
import threading
import urllib.parse
from urllib.parse import quote, unquote, urljoin
import importlib.util

import requests
import urllib3
urllib3.disable_warnings()

# 只有存在 Brotli 解码器时才声明 br，否则响应体无法解压
_ACCEPT_ENCODING = "gzip, deflate"
if importlib.util.find_spec("brotli") is not None or importlib.util.find_spec("brotlicffi") is not None:
    _ACCEPT_ENCODING += ", br"


class Spider:

    _TIMEOUT = 15
    _PAGE_SIZE = 24
    # 线路名与 chapters.resource_url 的 key：1=普快线路，21=超快线路
    _SOURCES = [("普快线路", "1"), ("超快线路", "21")]
    _SORTS = [("最新", "new"), ("人气", "hot"), ("评分", "score")]
    _FILTER_FIELDS = [("tag", "类型"), ("area", "地区"), ("year", "年代"),
                      ("source", "线路"), ("status", "状态")]
    _CHANNELS = [("2", "电视剧"), ("1", "电影"), ("3", "综艺"),
                 ("4", "动漫"), ("32", "纪录片")]
    _AREA_NAMES = ("国产", "欧美", "日本", "香港", "韩国", "泰国",
                   "台湾", "英国", "东南亚", "其它", "其他")
    _UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36")

    def __init__(self):
        self.host = "https://www.rytv.tv"
        self.ua = self._UA
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": _ACCEPT_ENCODING,
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="154", "Google Chrome";v="154"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Upgrade-Insecure-Requests": "1",
            "Referer": self.host + "/",
        }
        self.categories = [{"type_id": cid, "type_name": name} for cid, name in self._CHANNELS]
        self.filters = {cid: [] for cid, _ in self._CHANNELS}
        self._cookie_lock = threading.Lock()
        self._session = None
        self._filter_cache_file = None
        self._filter_cache_data = None
        self._hot_raw = None
        self._mcache = {}

    # ---------- 基础接口 ----------
    def getName(self):
        return "如意视频"

    def getDependence(self):
        return []

    def init(self, extend=""):
        ext = {}
        try:
            if isinstance(extend, str) and extend.strip().startswith("{"):
                ext = json.loads(extend)
            elif isinstance(extend, dict):
                ext = extend
        except Exception:
            ext = {}

        if isinstance(ext, dict):
            if ext.get("host"):
                self.host = str(ext["host"]).strip().rstrip("/")
                self.headers["Referer"] = self.host + "/"
            if ext.get("ua"):
                self.ua = str(ext["ua"]).strip()
                self.headers["User-Agent"] = self.ua

        self._mcache.clear()
        self._hot_raw = None
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self._filter_cache_file = os.path.join(base_dir, ".rysp_filter_cache.json")
        except Exception:
            self._filter_cache_file = None
        return None

    # ---------- 会话 ----------
    @property
    def session(self):
        if self._session is None:
            with self._cookie_lock:
                if self._session is None:
                    s = requests.Session()
                    s.headers.clear()
                    ua = self.headers.get("User-Agent") or self._UA
                    s.headers.update({
                        "User-Agent": ua,
                        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    })
                    s.verify = False
                    self._session = s
        return self._session

    @session.setter
    def session(self, value):
        self._session = value

    def _page_header(self, referer=None):
        ua = self.headers.get("User-Agent") or self._UA
        ref = str(referer or "").strip()
        if not ref.startswith("http"):
            ref = self.host.rstrip("/") + "/"
        return {
            "User-Agent": ua,
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": ref,
        }

    def _get(self, path, referer=None, xhr=False):
        base = self.host.rstrip("/")
        clean_path = "/" + str(path or "").lstrip("/")
        url = base + clean_path

        hd = self._page_header(referer or (base + "/video/list?channel_id=1"))
        if xhr:
            hd["X-Requested-With"] = "XMLHttpRequest"
            hd["Accept"] = "application/json, text/javascript, */*; q=0.01"
            hd["Sec-Fetch-Dest"] = "empty"
            hd["Sec-Fetch-Mode"] = "cors"
            hd["Sec-Fetch-Site"] = "same-origin"
        else:
            hd["Accept"] = self.headers["Accept"]

        last_err = None
        for attempt in range(3):
            try:
                r = self.session.get(url, headers=hd, timeout=self._TIMEOUT, verify=False)
                r.raise_for_status()
                r.encoding = r.apparent_encoding or "utf-8"
                return r.text
            except Exception as e:
                last_err = e
                time.sleep(0.5 * (attempt + 1))
        raise last_err

    def _json(self, path, referer=None):
        text = self._get(path, referer=referer, xhr=True)
        return json.loads(text)

    def _cate_json(self, **params):
        q = {
            "page_num": 1,
            "page_size": self._PAGE_SIZE,
            "sort": "new",
            "sorttype": "desc",
            "channel_id": "",
            "tag": "",
            "area": "",
            "year": "",
            "source": "",
            "status": "",
        }
        q.update(params or {})
        cid = str(q.get("channel_id") or 1)
        ref = f"{self.host.rstrip('/')}/video/list?channel_id={cid}"
        data = self._json("/video/refresh-cate?" + urllib.parse.urlencode(q, doseq=True), referer=ref)
        if isinstance(data, dict):
            if isinstance(data.get("data"), dict):
                return data["data"]
            if isinstance(data.get("list"), list):
                return data
        return {}

    # ---------- 筛选器 ----------
    def _read_filter_box(self, search_box):
        box = {}
        if not isinstance(search_box, (list, tuple)):
            return box
        for grp in search_box:
            if not isinstance(grp, dict):
                continue
            field = grp.get("field")
            if not field or field == "sort" or field in box:
                continue
            lst = grp.get("list")
            if not isinstance(lst, (list, tuple)):
                continue
            vals = []
            for x in lst:
                if not isinstance(x, dict):
                    continue
                disp = str(x.get("display") or "").strip()
                if not disp or disp == "全部":
                    continue
                val = "" if x.get("value") is None else str(x.get("value")).strip()
                vals.append({"n": disp, "v": val})
            if vals:
                box[field] = vals
        return box

    def _build_filters(self, seed_data=None):
        data = seed_data if isinstance(seed_data, dict) else {}
        if not data.get("search_box"):
            try:
                data = self._cate_json(page_size=1) or {}
            except Exception:
                data = {}
        box = self._read_filter_box(data.get("search_box") or [])
        out = {}
        sort_group = {
            "key": "sort",
            "name": "排序",
            "value": [{"n": n, "v": v} for n, v in self._SORTS],
        }
        for cid, _ in self._CHANNELS:
            groups = [sort_group]
            for field, label in self._FILTER_FIELDS:
                values = box.get(field) or []
                if values:
                    groups.append({"key": field, "name": label, "value": values})
            out[cid] = groups
        return out

    def _load_filters(self, seed_data=None):
        if self._filter_cache_data is not None:
            return self._filter_cache_data

        path = self._filter_cache_file
        if path and os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("date") == time.strftime("%Y%m%d") and isinstance(cached.get("filters"), dict):
                    self._filter_cache_data = cached["filters"]
                    return self._filter_cache_data
            except Exception:
                pass

        out = self._build_filters(seed_data=seed_data)
        self._filter_cache_data = out
        if path:
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"date": time.strftime("%Y%m%d"), "filters": out}, f, ensure_ascii=False)
            except Exception:
                pass
        return out

    # ---------- 首页 ----------
    def _fetch_hot_raw(self):
        if self._hot_raw is None:
            try:
                self._hot_raw = self._cate_json(page_size=self._PAGE_SIZE, sort="hot") or {}
            except Exception:
                self._hot_raw = {}
        return self._hot_raw

    def homeContent(self, filter=None):
        raw = self._fetch_hot_raw()
        try:
            self.filters = self._load_filters(seed_data=raw)
        except Exception:
            self.filters = {cid: [] for cid, _ in self._CHANNELS}

        cards = self._cards(raw.get("list") or [])
        # 若 API 列表为空，尝试降级抓取网页首页 HTML
        if not cards:
            try:
                html = self._get("/")
                cards = self._cards_from_html(html)
            except Exception:
                cards = []

        return {"class": self.categories, "list": cards, "filters": self.filters}

    def homeVideoContent(self):
        raw = self._fetch_hot_raw()
        cards = self._cards(raw.get("list") or [])
        if not cards:
            try:
                html = self._get("/")
                cards = self._cards_from_html(html)
            except Exception:
                cards = []
        return {"list": cards}

    # ---------- 分类列表 ----------
    def categoryContent(self, tid, pg=1, filter=None, extend=None):
        if not isinstance(extend, dict):
            extend = {}
        page = self._safe_page(pg, 1)
        tid = str(tid or "").strip()

        try:
            data = self._cate_json(
                channel_id=tid,
                page_num=page,
                sort=self._ext(extend, "sort") or "new",
                tag=self._ext(extend, "tag"),
                area=self._ext(extend, "area"),
                year=self._ext(extend, "year"),
                source=self._ext(extend, "source"),
                status=self._ext(extend, "status"),
            )
        except Exception:
            data = {}

        cards = self._cards((data or {}).get("list") or [])
        # 降级：若第 1 页接口未返回数据，尝试解析分类页 HTML
        if not cards and page == 1:
            try:
                html = self._get(f"/video/list?channel_id={urllib.parse.quote(tid)}")
                cards = self._cards_from_html(html)
            except Exception:
                cards = []

        data = data or {}
        total = data.get("total_count") or len(cards)
        cur = self._safe_page(data.get("current_page"), page)
        pcount = self._safe_page(data.get("total_page"), 1)
        return {
            "page": cur,
            "pagecount": pcount,
            "limit": self._PAGE_SIZE,
            "total": total,
            "list": cards,
        }

    # ---------- 搜索 ----------
    def searchContent(self, key, quick=False, pg="1"):
        key = "" if key is None else str(key).strip()
        page = self._safe_page(pg, 1)
        if not key:
            return {"list": [], "page": page, "pagecount": 1, "limit": self._PAGE_SIZE, "total": 0}

        q = urllib.parse.urlencode({
            "keyword": key,
            "page_num": page,
            "page_size": self._PAGE_SIZE,
            "sort": "new",
            "sorttype": "desc",
            "type": "",
        })
        ref = f"{self.host.rstrip('/')}/video/search-result?keyword={urllib.parse.quote(key)}"
        try:
            html = self._get("/video/refresh-video?" + q, xhr=True, referer=ref)
            cards = self._cards_from_html(html)
        except Exception:
            cards = []

        return {
            "list": cards,
            "page": page,
            "pagecount": page + (1 if len(cards) >= self._PAGE_SIZE else 0),
            "limit": self._PAGE_SIZE,
            "total": len(cards),
        }

    # ---------- 详情 ----------
    def _empty_vod(self, vid):
        return {
            "vod_id": vid, "vod_name": "", "vod_pic": "",
            "vod_remarks": "", "type_name": "", "vod_class": "",
            "vod_year": "", "vod_area": "", "vod_actor": "",
            "vod_director": "", "vod_content": "",
            "vod_play_from": "", "vod_play_url": "",
        }

    def detailContent(self, ids):
        if isinstance(ids, (list, tuple)):
            vid = str(ids[0]) if ids and ids[0] is not None else ""
        else:
            vid = "" if ids is None else str(ids)
        vid = vid.split("$$")[0].strip()
        if not vid:
            return {"list": [self._empty_vod("")]}

        try:
            page = self._get("/video/detail?video_id=" + urllib.parse.quote(vid))
        except Exception:
            return {"list": [self._empty_vod(vid)]}

        info = self._info_of(page, vid)
        chapters = self._chapters_of(page)

        names = []
        groups = []
        for name, key in self._SOURCES:
            eps = []
            for idx, ch in enumerate(chapters, 1):
                if not isinstance(ch, dict):
                    continue
                ru = ch.get("resource_url")
                if not isinstance(ru, dict):
                    continue
                url = ru.get(key)
                if url:
                    eps.append(f"{self._ep_name(ch, idx)}${str(url).strip()}")
            if eps:
                names.append(name)
                groups.append("#".join(eps))

        return {"list": [{
            "vod_id": vid,
            "vod_name": info.get("name", ""),
            "vod_pic": info.get("pic", ""),
            "vod_remarks": info.get("score", ""),
            "type_name": info.get("types", ""),
            "vod_class": info.get("types", ""),
            "vod_year": info.get("year", ""),
            "vod_area": info.get("area", ""),
            "vod_actor": info.get("actor", ""),
            "vod_director": info.get("director", ""),
            "vod_content": info.get("intro", ""),
            "vod_play_from": "$$$".join(names),
            "vod_play_url": "$$$".join(groups),
        }]}

    def _chapters_of(self, page):
        if not isinstance(page, str) or not page:
            return []
        try:
            i = page.find("// console.log([{")
            if i < 0:
                return []
            start = page.index("[", i)
            end = self._match_bracket(page, start)
            if end <= start:
                return []
            data = json.loads(page[start:end + 1])
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _match_bracket(self, s, start):
        if not isinstance(s, str) or start < 0 or start >= len(s):
            return -1
        depth = 0
        in_str = False
        esc = False
        for k in range(start, len(s)):
            c = s[k]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == '"':
                    in_str = False
                continue
            if c == '"':
                in_str = True
            elif c in "[{":
                depth += 1
            elif c in "]}":
                depth -= 1
                if depth == 0:
                    return k
        return -1

    def _info_of(self, page, vid):
        if not isinstance(page, str):
            page = ""
        try:
            name = ""
            m = re.search(r'<div class="play-name"[^>]*>\s*([^<]{1,80}?)\s*</div>', page)
            if m:
                name = self._text(m.group(1))
            if not name:
                m = re.search(r"<title>\s*(.*?)\s*-\s*如意视频", page, re.S)
                name = self._text(m.group(1)) if m else vid

            tags = []
            m = re.search(r'<div class="GNbox-type"[^>]*>([\s\S]*?)</div>', page)
            if m:
                tags = [self._text(x) for x in re.findall(r"<span[^>]*>([\s\S]*?)</span>", m.group(1))]
            tags = [t for t in tags if t]

            year = next((t for t in tags if re.fullmatch(r"\d{4}", t)), "")
            area = ""
            cls = []
            for t in tags:
                if t == year:
                    continue
                if t in self._AREA_NAMES:
                    area = t
                else:
                    cls.append(t)

            pic = ""
            m = re.search(r'<div class="GNbox-xq-img"[\s\S]{0,400}?originalSrc="([^"]+)"', page)
            if m:
                pic = self._fix_url(m.group(1))

            score = ""
            m = re.search(r'<div class="GNbox-PF"[^>]*>\s*<span>([\d.]+)</span>', page)
            if m:
                score = m.group(1)

            return {
                "name": name,
                "pic": pic,
                "score": score,
                "types": " ".join(cls),
                "year": year,
                "area": area,
                "actor": self._field(page, "主演"),
                "director": self._field(page, "导演"),
                "intro": self._field(page, "简介"),
            }
        except Exception:
            return {
                "name": vid, "pic": "", "score": "", "types": "",
                "year": "", "area": "", "actor": "", "director": "", "intro": "",
            }

    def _field(self, page, label):
        m = re.search(label + r"[：:]\s*<span>\s*([\s\S]*?)\s*</span>", page)
        return self._text(m.group(1)) if m else ""

    def _ep_name(self, ch, index):
        if isinstance(ch, dict):
            name = str(ch.get("title") or "").strip()
            if name:
                return name
        try:
            return f"第{int(index):02d}集"
        except Exception:
            return "正片"

    # ---------- 播放与本地代理 ----------
    def getProxyUrl(self, local=True):
        try:
            from com.github.catvod import Proxy as _CatProxy
            try:
                return str(_CatProxy.getUrl(local)) + "?do=py"
            except Exception:
                return str(_CatProxy.getUrl()) + "?do=py"
        except Exception:
            return "http://127.0.0.1:9978/proxy?do=py"

    def _proxy_url(self, url, kind="media", referer=None):
        root = self.getProxyUrl(True) or "http://127.0.0.1:9978/proxy?do=py"
        sep = "&" if "?" in root else "?"
        u = f"{root}{sep}type={kind}&url={quote(str(url or ''), safe='')}"
        ref = str(referer or "").strip()
        if ref.startswith("http"):
            u += "&referer=" + quote(ref, safe="")
        return u

    def _media_header(self, url="", referer=""):
        ua = self.headers.get("User-Agent") or self._UA
        ref = str(referer or "").strip()
        base = self.host.rstrip("/")
        return {
            "User-Agent": ua,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": base,
            "Referer": ref if ref.startswith("http") else (base + "/"),
        }

    def _fetch_bin(self, url, head, timeout=15):
        for _ in range(3):
            try:
                r = self.session.get(url, headers=head, timeout=timeout, verify=False)
                if r.status_code == 200 and r.content:
                    return r
            except Exception:
                continue
        return None

    def _sub_url(self, url, body):
        m = re.search(r'#EXT-X-STREAM-INF[^\n]*\n\s*([^\n#]+)', body or "")
        if not m:
            return ""
        path = m.group(1).strip()
        return path if path.startswith("http") else urljoin(url, path)

    def _playlist(self, url, head):
        r = self._fetch_bin(url, head, 20)
        if r is None:
            return url, ""
        text = r.text or ""
        if "#EXTINF" not in text:
            return url, text
        if "#EXT-X-STREAM-INF" not in text:
            return url, text
        sub = self._sub_url(url, text)
        if not sub:
            return url, text
        r2 = self._fetch_bin(sub, head, 20)
        t2 = r2.text if r2 is not None else ""
        if r2 is None or "#EXTINF" not in t2:
            return url, text
        self._mcache[url] = sub
        return sub, t2

    def _rewrite_m3u8(self, text, base, referer=""):
        root = self.getProxyUrl(True) or "http://127.0.0.1:9978/proxy?do=py"
        sep = "&" if "?" in root else "?"
        ref = str(referer or "").strip()
        if not ref.startswith("http"):
            ref = ""

        out = []
        for raw in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            line = raw.strip()
            if not line:
                out.append("")
                continue
            if line.startswith("#"):
                if "URI=" in line:
                    def _rp(m):
                        v = m.group(2)
                        if not v.startswith("http"):
                            v = urljoin(base, v)
                        return m.group(1) + self._proxy_url(v, "media", ref) + m.group(3)
                    line = re.sub(r'(URI=")([^"]+)(")', _rp, line)
                out.append(line)
                continue
            seg_url = line if line.startswith("http") else urljoin(base, line)
            ts_proxy = f"{root}{sep}type=ts&url={quote(seg_url, safe='')}"
            if ref:
                ts_proxy += "&referer=" + quote(ref, safe="")
            out.append(ts_proxy)

        body = "\n".join(out)
        return body if body.endswith("\n") else body + "\n"

    def playerContent(self, flag, id, vipFlags=None):
        url = str(id or "").strip()
        if url.startswith("//"):
            url = "https:" + url
        if not url or not self._is_media(url):
            return {"parse": 1, "jx": 0, "playUrl": "", "url": url, "header": self._media_header()}

        base_ref = self.host.rstrip("/") + "/"
        try:
            base, body = self._playlist(url, self._media_header(url, base_ref))
        except Exception:
            base, body = url, ""

        target = base if (body and "#EXTINF" in body) else url
        return {
            "parse": 0,
            "jx": 0,
            "playUrl": "",
            "url": self._proxy_url(target, "m3u8", base_ref),
            "header": self._media_header(target, base_ref),
            "format": "application/x-mpegURL",
        }

    def localProxy(self, param):
        try:
            if isinstance(param, str):
                param = json.loads(param)
            if not isinstance(param, dict):
                param = {}

            kind = param.get("type") or param.get("action") or param.get("do") or ""
            if isinstance(kind, list):
                kind = kind[0] if kind else ""
            kind = str(kind or "").strip().lower()

            url = param.get("url") or ""
            if isinstance(url, list):
                url = url[0] if url else ""
            url = unquote(str(url or "")).replace("\\/", "/").strip()

            referer = param.get("referer") or param.get("ref") or ""
            if isinstance(referer, list):
                referer = referer[0] if referer else ""
            referer = unquote(str(referer or "")).strip()

            if not url:
                return [404, "text/plain", "Not Found"]
            if url.startswith("//"):
                url = "https:" + url
            if not url.startswith("http"):
                return [404, "text/plain", "Unsupported"]

            if not kind or kind in ("py", "proxy", "media"):
                kind = "m3u8" if "m3u8" in url.lower() else "ts"

            head = self._media_header(url, referer)
            if kind == "m3u8" or ".m3u8" in url.lower():
                base, body = self._playlist(url, head)
                if not body:
                    return [404, "text/plain", "Fetch Failed"]
                data = self._rewrite_m3u8(body, base, referer)
                return [200, "application/vnd.apple.mpegurl", data]

            r = self._fetch_bin(url, head, 20)
            if r is None or not r.content:
                return [404, "text/plain", "Fetch Failed"]
            body = bytes(r.content)
            mime = "video/mp2t" if body[:1] == b"\x47" else "application/octet-stream"
            return [200, mime, body]
        except Exception:
            return [500, "text/plain", "proxy error"]

    def _is_media(self, url):
        low = str(url or "").lower()
        return any(ext in low for ext in (".m3u8", ".mp4", ".flv", ".ts"))

    def isVideoFormat(self, url):
        return self._is_media(url)

    def manualVideoCheck(self):
        return False

    def action(self, action):
        return {}

    def destroy(self):
        with self._cookie_lock:
            if self._session is not None:
                try:
                    self._session.close()
                except Exception:
                    pass
                self._session = None
        self._mcache.clear()
        self._filter_cache_data = None
        self._hot_raw = None
        return None

    # ---------- 辅助 ----------
    def _fix_url(self, url):
        if url is None:
            return ""
        url = str(url).strip()
        if not url:
            return ""
        if url.startswith("//"):
            return "https:" + url
        if url.startswith("/"):
            return self.host.rstrip("/") + url
        return url

    def _safe_page(self, pg, default=1):
        try:
            return max(int(str(pg if pg is not None else default).strip() or default), 1)
        except Exception:
            return default

    def _ext(self, extend, key):
        v = (extend or {}).get(key, "")
        if isinstance(v, (list, tuple)):
            v = v[0] if v else ""
        return "" if v is None else str(v).strip()

    def liveContent(self, url):
        return ""

    def proxy(self, param):
        return self.localProxy(param)

    def _text(self, s):
        if s is None:
            return ""
        s = re.sub(r"<[^>]+>", " ", str(s))
        s = (s.replace("&nbsp;", " ")
              .replace("&amp;", "&")
              .replace("&quot;", '"')
              .replace("&#39;", "'")
              .replace("&lt;", "<")
              .replace("&gt;", ">"))
        return re.sub(r"\s+", " ", s).strip()

    def _cards(self, items):
        out = []
        seen = set()
        if not isinstance(items, (list, tuple)):
            return out
        for it in items:
            if not isinstance(it, dict):
                continue
            vid = it.get("video_id") or it.get("id") or it.get("vod_id")
            vid = "" if vid is None else str(vid).strip()
            if not vid or vid in seen:
                continue
            seen.add(vid)

            name = it.get("video_name") or it.get("name") or it.get("vod_name") or ""
            pic = it.get("cover") or it.get("pic") or it.get("vod_pic") or it.get("img") or ""
            remark = it.get("score") or it.get("vod_remarks") or ""
            remark = "" if remark is None else str(remark).strip()
            hot = "" if it.get("play_times") is None else str(it.get("play_times")).strip()

            out.append({
                "vod_id": vid,
                "vod_name": self._text(name),
                "vod_pic": self._fix_url(pic),
                "vod_remarks": f"评分{remark}" if remark else hot,
                "vod_class": self._text(it.get("category") or it.get("vod_class") or ""),
                "vod_year": str(it.get("year") or ""),
                "vod_area": str(it.get("area") or ""),
                "vod_actor": self._text(it.get("artist") or it.get("actor") or "").replace("演员:", "").strip()[:120],
                "vod_director": self._text(it.get("director") or "").replace("导演:", "").strip()[:60],
                "vod_content": self._text(it.get("intro") or it.get("vod_content") or ""),
            })
        return out

    def _cards_from_html(self, html):
        out = []
        seen = set()
        if not isinstance(html, str) or not html:
            return out
        blocks = html.split('<li class="Movie-list">')[1:]
        if not blocks:
            blocks = re.findall(r'<li[^>]*class="[^"]*Movie-list[^"]*"[\s\S]{0,4000}?</li>', html)
        for blk in blocks:
            vid = re.search(r'video_id=(\d+)', blk)
            if not vid or vid.group(1) in seen:
                continue
            seen.add(vid.group(1))
            name = re.search(r'Movie-name01[^>]*>\s*([^<]+)', blk)
            pic = re.search(r'(?:originalSrc|data-src|src)="([^"]+\.(?:jpg|jpeg|png|webp|gif)[^"]*)"', blk)
            score = re.search(r'class="oth-time"[\s\S]{0,160}?>\s*([\d.]+)\s*<', blk)
            cat = re.search(r'<ul[^>]*class="[^"]*Movie-type[^"]*"[\s\S]*?</ul>', blk)
            actor = re.search(r'Movie-star[\s\S]{0,2000}?主演[：:]\s*([\s\S]{0,600}?)</div>', blk)
            intro = re.search(r'Movie-content[\s\S]{0,2400}?简介[：:]\s*([\s\S]{0,900}?)</span>', blk)
            hot = re.search(r'热度[：:]\s*([\d.]+)', blk)
            out.append({
                "vod_id": vid.group(1),
                "vod_name": self._text(name.group(1)) if name else "",
                "vod_pic": self._fix_url(pic.group(1)) if pic else "",
                "vod_remarks": f"评分{score.group(1)}" if score else (f"热度{hot.group(1)}" if hot else ""),
                "vod_class": self._text(cat.group(0)) if cat else "",
                "vod_year": "",
                "vod_area": "",
                "vod_actor": self._text(actor.group(1))[:120] if actor else "",
                "vod_director": "",
                "vod_content": self._text(intro.group(1))[:400] if intro else "",
            })
        return out

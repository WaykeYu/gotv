# -*- coding: utf-8 -*-
"""
红果短剧 (hongguo / www.hongguoapp.cn) —— Yumilo Windows / TVBox / FongMi 完整版
（2026-11 针对 api.php=closed 的网页直解版）：
1. 已知 api.php/provide/vod 返回 closed，详情与选集改由 /voddetail/{vid}.html 与
   /vodplay/{vid}-1-1.html 双向提取，确保完整拿到全集列表。
2. playerContent 完整解析播放页内的 player_aaaa（支持 encrypt=1 URL解码、encrypt=2 Base64解码）
   及多层 iframe / JS 跳转，提取真实 .m3u8 / .mp4 直链（parse=0）。
3. 详情页【简介】顶部附带简短播放页诊断摘要，若遇到特殊加密播放器可一眼识别。
"""
import re
import sys
import json
import time
import base64
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import quote, unquote, urljoin
from lxml import etree

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    from spider import Spider as BaseSpider


class Spider(BaseSpider):
    _RE_TID = re.compile(r"/(?:vodshow|vodtype|type|show/id|type/id)/(\d+)")
    _RE_VID = re.compile(r"/(?:voddetail|detail/id|vod/detail/id)/(\d+)|/id/(\d+)\.html")
    _RE_STYLE_URL = re.compile(r"url\(['\"]?([^'\")]+)['\"]?\)")
    _RE_YEAR = re.compile(r"((?:19|20)\d{2})")
    _RE_PLAYER_JSON = re.compile(r'player_[a-z0-9_]+\s*=\s*(\{.*?\})\s*(?:;|</script>)', re.S)
    _RE_JS_URL = re.compile(r"""(?:var|let|const)\s+(?:url|play_url|video_url|main|vurl)\s*=\s*['"]([^'"]+)['"]""")
    _RE_M3U8 = re.compile(r'(https?[^"\'\s\\<>]+\.m3u8[^"\'\s\\<>]*)')
    _RE_MP4 = re.compile(r'(https?[^"\'\s\\<>]+\.mp4[^"\'\s\\<>]*)')
    _RE_IFRAME = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)

    _VIRTUAL_CATS = [
        ("51", "全部短剧"),
        ("51:都市", "都市"),
        ("51:古装", "古装"),
        ("51:逆袭", "逆袭"),
        ("51:甜宠", "甜宠"),
        ("51:战神", "战神"),
        ("51:重生", "重生"),
        ("51:总裁", "总裁"),
        ("51:家庭", "家庭"),
    ]

    def getName(self):
        return "红果"

    def init(self, extend=""):
        self.host = "https://www.hongguoapp.cn"
        self.hosts = ["https://www.hongguoapp.cn"]
        try:
            o = json.loads(extend) if extend else {}
            if isinstance(o, dict) and o.get("host"):
                self.host = o["host"].rstrip("/")
                self.hosts = [self.host] + [h for h in self.hosts if h != self.host]
        except Exception:
            pass

        # 保留手机端 UA（该站移动端模板对详情/播放页兼容性最佳）
        self.ua = (
            "Mozilla/5.0 (Linux; Android 12; SM-G991B) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
        )
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self._json_headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "X-Requested-With": "XMLHttpRequest",
        }

        self._sess = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
        self._sess.mount("http://", adapter)
        self._sess.mount("https://", adapter)
        self._sess.headers.update(self.headers)

        self._search_cache = {}
        self._ssl_bad_domains = set()

    # ---------- 基础工具 ----------
    def _fix(self, u):
        if not u:
            return ""
        u = str(u).strip().replace("\\/", "/")
        if "url(" in u:
            m = self._RE_STYLE_URL.search(u)
            if m:
                u = m.group(1).strip()
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def _is_cf(self, html):
        if not html:
            return False
        head = html[:4000]
        return "Just a moment" in head or "challenges.cloudflare.com" in head or "Attention Required!" in head

    def _fetch(self, url, timeout=12, headers=None, retries=2):
        last = ""
        req_headers = headers or self.headers
        attempts = max(1, int(retries or 1))

        for i in range(attempts):
            try:
                r = self._sess.get(
                    url, headers=req_headers, timeout=timeout,
                    verify=False, allow_redirects=True
                )
                r.encoding = "utf-8"
                last = r.text or ""
                if last and (len(last) > 1500 or self._is_cf(last)):
                    return last
            except Exception:
                pass
            if i < attempts - 1:
                time.sleep(0.5 * (i + 1))

        if last and len(last) > 1500:
            return last

        try:
            r = requests.get(
                url, headers=req_headers, timeout=timeout,
                verify=False, allow_redirects=True
            )
            r.encoding = "utf-8"
            return r.text or last
        except Exception:
            return last

    def _fetch_json(self, url, timeout=8, retries=2, fallback_direct=True):
        attempts = max(1, int(retries or 1))
        for i in range(attempts):
            try:
                r = self._sess.get(
                    url, headers=self._json_headers, timeout=timeout,
                    verify=False, allow_redirects=True
                )
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, dict) and j.get("code") == 1 and isinstance(j.get("list"), list):
                        return j
            except Exception:
                if i < attempts - 1:
                    time.sleep(0.5 * (i + 1))

        if fallback_direct:
            try:
                r = requests.get(
                    url, headers=self._json_headers, timeout=timeout,
                    verify=False, allow_redirects=True
                )
                if r.status_code == 200:
                    j = r.json()
                    if isinstance(j, dict) and j.get("code") == 1 and isinstance(j.get("list"), list):
                        return j
            except Exception:
                pass
        return {}

    def _get(self, url):
        html = self._fetch(url)
        if html and len(html) > 1500:
            return html
        for h in self.hosts:
            if h == self.host:
                continue
            t = self._fetch(url.replace(self.host, h, 1), timeout=8, retries=1)
            if t and len(t) > 1500 and not self._is_cf(t) and "404 Not Found" not in t[:600]:
                self.host = h
                self.headers["Referer"] = h + "/"
                self._json_headers["Referer"] = h + "/"
                return t
        return html

    def _fix_ssl_url(self, url, referer=""):
        if not url or not url.startswith("https://"):
            return url
        try:
            domain = url.split("/")[2]
        except Exception:
            return url

        is_bad = domain in self._ssl_bad_domains
        if not is_bad:
            try:
                requests.head(
                    url,
                    headers={"User-Agent": self.ua, "Referer": referer or self.host + "/"},
                    timeout=3,
                    verify=True,
                    allow_redirects=True,
                )
                return url
            except requests.exceptions.SSLError:
                self._ssl_bad_domains.add(domain)
                is_bad = True
            except Exception:
                return url

        if is_bad:
            http_url = "http://" + url[8:]
            try:
                r = requests.head(
                    http_url,
                    headers={"User-Agent": self.ua, "Referer": referer or self.host + "/"},
                    timeout=3,
                    allow_redirects=True,
                )
                if r.status_code < 400:
                    return http_url
            except Exception:
                pass
            return f"proxy://do=hongguo&url={quote(url)}&ref={quote(referer or self.host + '/')}"

        return url

    # ---------- ID 解析 ----------
    def _tid(self, href):
        m = self._RE_TID.search(href or "")
        return m.group(1) if m else ""

    def _vid(self, href):
        m = self._RE_VID.search(href or "")
        if not m:
            return ""
        return m.group(1) or m.group(2) or ""

    # ---------- 主接口（分类 + 筛选 + 列表） ----------
    def homeContent(self, filter):
        cls = [{"type_id": cid, "type_name": cname} for cid, cname in self._VIRTUAL_CATS]
        filters = {
            "51": [
                {
                    "key": "class",
                    "name": "题材",
                    "value": [
                        {"n": "全部", "v": ""},
                        {"n": "都市", "v": "都市"},
                        {"n": "古装", "v": "古装"},
                        {"n": "逆袭", "v": "逆袭"},
                        {"n": "甜宠", "v": "甜宠"},
                        {"n": "战神", "v": "战神"},
                        {"n": "重生", "v": "重生"},
                        {"n": "总裁", "v": "总裁"},
                        {"n": "家庭", "v": "家庭"},
                    ],
                },
                {
                    "key": "by",
                    "name": "排序",
                    "value": [
                        {"n": "最新", "v": "time"},
                        {"n": "最热", "v": "hits"},
                        {"n": "评分", "v": "score"},
                    ],
                },
            ]
        }
        cat_res = self.categoryContent("51", 1, False, {})
        return {"class": cls, "list": cat_res.get("list", []), "filters": filters}

    def homeVideoContent(self):
        return {"list": self.categoryContent("51", 1, False, {}).get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        extend = extend or {}
        raw_tid = str(tid or "51")

        sub_class = ""
        if ":" in raw_tid:
            real_tid, sub_class = raw_tid.split(":", 1)
        else:
            real_tid = raw_tid

        v_class = extend.get("class") or sub_class
        v_by = extend.get("by") or ""

        url = f"{self.host}/index.php/ajax/data?mid=1&limit=24&tid={quote(real_tid)}"
        if pg > 1:
            url += f"&page={pg}"
        if v_class:
            url += f"&class={quote(v_class)}"
        if v_by:
            url += f"&by={quote(v_by)}"

        j = self._fetch_json(url)
        if j and j.get("list"):
            items = []
            for it in j["list"]:
                vid = str(it.get("vod_id", "") or "")
                name = str(it.get("vod_name", "") or "").strip()
                if not vid or not name:
                    continue
                item = {
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": self._fix(it.get("vod_pic", "") or ""),
                }
                rm = str(it.get("vod_remarks", "") or "").strip()
                if rm:
                    item["vod_remarks"] = rm
                items.append(item)

            pagecount = int(j.get("pagecount") or pg)
            total = int(j.get("total") or 0) or pagecount * 24
            return {
                "page": pg,
                "pagecount": pagecount,
                "limit": 24,
                "total": total,
                "list": items,
            }

        return {"page": pg, "pagecount": pg, "limit": 24, "total": 0, "list": []}

    # ---------- 详情与选集解析（同时兼容 detail 页与 play 页提取全集） ----------
    def _extract_episodes_from_html(self, html):
        eps, seen_ep = [], set()
        fallback_btn = None
        if not html or self._is_cf(html):
            return eps

        try:
            tree = etree.HTML(html)
        except Exception:
            tree = None

        if tree is not None:
            # 优先匹配海螺(conch)与其他常见模板播放列表容器
            play_nodes = tree.xpath(
                '//*[contains(@class,"hl-plays-list") or contains(@class,"playlist") '
                'or contains(@class,"play-list") or contains(@id,"playlist")]'
                '//a[contains(@href,"/vodplay/") or contains(@href,"/vod/play/") or contains(@href,"/play/")]'
            )
            if not play_nodes:
                play_nodes = tree.xpath(
                    '//a[contains(@href,"/vodplay/") or contains(@href,"/vod/play/") or contains(@href,"/play/")]'
                )

            for a in play_nodes:
                t = "".join(a.xpath(".//text()")).strip()
                h = self._fix(a.get("href", "") or "")
                if not t or not h:
                    continue
                if "播放" in t and len(t) >= 4:
                    if not fallback_btn:
                        fallback_btn = (t, h)
                    continue
                if h not in seen_ep:
                    seen_ep.add(h)
                    eps.append(f"{t}${h}")

        if not eps:
            for m in re.finditer(
                r'href="([^"]*/(?:vodplay|vod/play|play)/[^"]*\.html)"[^>]*>([^<]{1,30})</a>',
                html
            ):
                t = m.group(2).strip()
                h = self._fix(m.group(1))
                if not t:
                    continue
                if "播放" in t and len(t) >= 4:
                    if not fallback_btn:
                        fallback_btn = (t, h)
                    continue
                if h not in seen_ep:
                    seen_ep.add(h)
                    eps.append(f"{t}${h}")

        if not eps and fallback_btn:
            eps.append(f"第1集${fallback_btn[1]}")
        return eps

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        result = {"list": []}
        if not vid:
            return result

        num_vid = self._vid(vid) or vid
        detail_url = f"{self.host}/voddetail/{num_vid}.html"
        play1_url = f"{self.host}/vodplay/{num_vid}-1-1.html"

        html = self._get(detail_url)
        play1_html = ""

        # 如果 detail 页被 CF 拦或没抓到，直接改抓第 1 集播放页（play 页通常也带有完整选集列表与剧名）
        if not html or self._is_cf(html) or len(html) < 1500:
            play1_html = self._get(play1_url)
            if play1_html and not self._is_cf(play1_html) and len(play1_html) > 1500:
                html = play1_html

        if not html or self._is_cf(html):
            return result

        try:
            tree = etree.HTML(html)
        except Exception:
            return result
        if tree is None:
            return result

        name = "".join(tree.xpath('//h2[contains(@class,"hl-dc-title")]//text() | //h1//text()')).strip()
        if not name:
            m = re.search(r"<title>([^<]+)</title>", html)
            if m:
                name = re.split(r"[-_|《]", m.group(1))[0].strip("《 ")
        if not name:
            name = f"短剧_{num_vid}"

        pic = ""
        for xp in (
            '//*[contains(@class,"hl-item-thumb")]/@data-original',
            '//*[contains(@class,"detail-pic")]//img/@data-original',
            '//*[contains(@class,"detail-pic")]//img/@src',
            '//*[@class="hl-topbg-pic"]/@style',
            '//meta[@property="og:image"]/@content',
        ):
            v = tree.xpath(xp)
            if v and v[0].strip():
                pic = v[0].strip()
                break

        actor = "/".join(t.strip() for t in tree.xpath('//li[contains(.,"主演")]//a/text()') if t.strip())
        director = "/".join(t.strip() for t in tree.xpath('//li[contains(.,"导演")]//a/text()') if t.strip())
        des = re.sub(r"^简介[：:\s]*", "", "".join(tree.xpath('//li[contains(.,"简介")]//text()')).strip()).strip()
        if not des:
            des = "".join(
                tree.xpath('//*[contains(@class,"detail-content") or contains(@class,"vod-content")]//text()')
            ).strip()[:1500]

        eps = self._extract_episodes_from_html(html)
        # 如果 detail 页没提取出完整集数，再从 play1 页提取
        if len(eps) <= 1 and not play1_html:
            play1_html = self._get(play1_url)
            more_eps = self._extract_episodes_from_html(play1_html)
            if len(more_eps) > len(eps):
                eps = more_eps

        if not eps:
            eps = [f"第1集${play1_url}"]

        # 顺便在简介头部附带第1集播放页的播放器快照，便于排查播放结构
        sample_p = play1_html or self._get(play1_url)
        m_pa = self._RE_PLAYER_JSON.search(sample_p or "")
        pa_hint = f"[播放器参数] {m_pa.group(1)[:180]}\n" if m_pa else f"[播放页状态] len={len(sample_p or '')}, cf={self._is_cf(sample_p)}\n"

        result["list"].append({
            "vod_id": num_vid,
            "vod_name": name,
            "vod_pic": self._fix(pic),
            "vod_actor": actor,
            "vod_director": director,
            "vod_content": pa_hint + des,
            "vod_play_from": "红果",
            "vod_play_url": "#".join(eps),
        })
        return result

    # ---------- 搜索 ----------
    def _search_all(self, key, limit=200, quick=False):
        clean_key = str(key or "").strip()
        if not clean_key:
            return [], 0

        limit = max(1, min(int(limit or 200), 200))
        cache_key = (clean_key, limit)
        now = time.time()

        cached = self._search_cache.get(cache_key)
        if cached and (now - cached[0] < 60):
            return cached[1], cached[2]

        if len(self._search_cache) > 30:
            self._search_cache = {k: v for k, v in self._search_cache.items() if now - v[0] < 60}

        q = quote(clean_key)
        url = f"{self.host}/index.php/ajax/suggest?mid=1&wd={q}&limit={limit}"

        if quick:
            j = self._fetch_json(url, timeout=6, retries=1, fallback_direct=False)
        else:
            j = self._fetch_json(url, timeout=10, retries=2, fallback_direct=True)

        if not j or not isinstance(j.get("list"), list):
            return [], 0

        items = []
        for it in j["list"]:
            vid = str(it.get("id", "") or "")
            name = str(it.get("name", "") or "").strip()
            if vid and name:
                items.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": self._fix(it.get("pic", "") or ""),
                })

        total = int(j.get("total") or 0) or len(items)
        if items:
            self._search_cache[cache_key] = (now, items, total)
        return items, total

    def _search_json(self, key, pg=1, page_size=20, fetch_limit=200, quick=False):
        items, total = self._search_all(key, limit=fetch_limit, quick=quick)
        pg = max(1, int(pg or 1))
        page_size = max(1, int(page_size or 20))
        start = (pg - 1) * page_size
        page_items = items[start:start + page_size]
        pagecount = max(1, -(-int(total) // page_size))
        return page_items, pg, pagecount, total

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        is_quick = bool(quick)
        fetch_limit = 60 if is_quick else 200

        items, page, pagecount, total = self._search_json(
            key, pg=pg, page_size=20, fetch_limit=fetch_limit, quick=is_quick
        )
        if items:
            return {
                "list": items,
                "page": page,
                "pagecount": pagecount,
                "limit": 20,
                "total": total,
            }
        return {"list": [], "page": pg}

    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)

    # ---------- 播放解析 ----------
    def _decode_player_url(self, raw_url, encrypt=0):
        if not raw_url:
            return ""
        u = str(raw_url).strip()
        try:
            enc = int(encrypt or 0)
        except Exception:
            enc = 0

        if enc == 1:
            u = unquote(u)
        elif enc == 2:
            try:
                u = unquote(base64.b64decode(u).decode("utf-8", errors="ignore"))
            except Exception:
                pass
        else:
            if "%3A%2F%2F" in u or "%2F" in u:
                u = unquote(u)
        return u.replace("\\/", "/").strip()

    def _extract_media_from_html(self, html, base_url=""):
        if not html:
            return ""

        for m in self._RE_PLAYER_JSON.finditer(html):
            try:
                obj = json.loads(m.group(1))
                raw_url = (obj.get("url") or "").split(";")[0]
                url = self._decode_player_url(raw_url, obj.get("encrypt", 0))
                if url:
                    return self._fix(url)
            except Exception:
                continue

        m_js = self._RE_JS_URL.search(html)
        if m_js:
            val = unquote(m_js.group(1).replace("\\/", "/")).strip()
            if val.startswith(("http", "//", "/")):
                return urljoin(base_url, val) if base_url else self._fix(val)

        for rx in (self._RE_M3U8, self._RE_MP4):
            m = rx.search(html)
            if m:
                return unquote(m.group(1).replace("\\/", "/")).strip()

        return ""

    def _resolve_jx_or_page(self, target_url, referer="", depth=0):
        if depth > 2 or not target_url:
            return ""

        if self.isVideoFormat(target_url):
            return self._fix(target_url)

        html = self._fetch(
            target_url,
            timeout=10,
            headers={"User-Agent": self.ua, "Referer": referer or self.host + "/"},
            retries=2,
        )
        if not html or self._is_cf(html):
            return ""

        extracted = self._extract_media_from_html(html, target_url)
        if extracted:
            if self.isVideoFormat(extracted):
                return extracted
            if extracted != target_url:
                return self._resolve_jx_or_page(extracted, referer=target_url, depth=depth + 1)

        m_if = self._RE_IFRAME.search(html)
        if m_if:
            fr = urljoin(target_url, m_if.group(1).strip())
            if fr != target_url:
                return self._resolve_jx_or_page(fr, referer=target_url, depth=depth + 1)

        return ""

    def _verify_stream(self, url, referer=""):
        if not url:
            return None
        path = url.lower().split("?")[0]
        header_candidates = [
            {"User-Agent": self.ua, "Referer": referer},
            {"User-Agent": self.ua, "Referer": self.host + "/"},
            {"User-Agent": self.ua},
        ]
        for hdrs in header_candidates:
            try:
                r = self._sess.get(
                    url, headers=hdrs, timeout=6, verify=False, stream=True, allow_redirects=True
                )
                if r.status_code in (200, 206):
                    ct = (r.headers.get("Content-Type") or "").lower()
                    chunk = next(r.iter_content(chunk_size=512), b"")
                    r.close()
                    if not path.endswith(".m3u8"):
                        if "text/html" not in ct:
                            return hdrs
                    else:
                        head_txt = chunk.decode("utf-8", errors="ignore").lstrip()
                        if head_txt.startswith("#EXTM3U"):
                            return hdrs
                else:
                    r.close()
            except Exception:
                continue
        return None

    def playerContent(self, flag, id, vipFlags):
        pid = str(id or "").strip()
        if pid.startswith("http"):
            target = pid
        elif pid.startswith("/"):
            target = self.host + pid
        else:
            target = f"{self.host}/vodplay/{pid}.html"

        media_url = self._resolve_jx_or_page(target, referer=self.host + "/")
        if media_url:
            best_hdr = self._verify_stream(media_url, target)
            if best_hdr is not None:
                safe_url = self._fix_ssl_url(media_url, best_hdr.get("Referer", ""))
                return {
                    "parse": 0,
                    "url": safe_url,
                    "header": best_hdr,
                }

        return {"parse": 0, "url": ""}

    def localProxy(self, param):
        if not param or param.get("do") != "hongguo":
            return None
        target = unquote(param.get("url", ""))
        ref = unquote(param.get("ref", self.host + "/"))
        if not target:
            return None

        try:
            r = self._sess.get(
                target,
                headers={"User-Agent": self.ua, "Referer": ref},
                timeout=15,
                verify=False,
                stream=True,
                allow_redirects=True,
            )
            ct = r.headers.get("Content-Type", "application/octet-stream")
            if ".m3u8" in target.lower() or "mpegurl" in ct.lower():
                text = r.text
                base_url = target.rsplit("/", 1)[0] + "/"
                lines = []
                for line in text.splitlines():
                    s = line.strip()
                    if s and not s.startswith("#"):
                        if not s.startswith("http"):
                            s = base_url + s.lstrip("/")
                        if s.startswith("https://"):
                            s = f"proxy://do=hongguo&url={quote(s)}&ref={quote(ref)}"
                        lines.append(s)
                    else:
                        lines.append(line)
                body = "\n".join(lines).encode("utf-8")
                return [200, "application/vnd.apple.mpegurl", body]

            return [r.status_code, ct, r.raw]
        except Exception:
            return None

    def isVideoFormat(self, url):
        if not url:
            return False
        path = url.lower().split("?")[0].split("#")[0]
        return path.endswith((".m3u8", ".mp4", ".m4v", ".flv", ".ts", ".webm", ".mov", ".mpd"))

    def manualVideoCheck(self):
        return False

    def getDependence(self):
        return []

    def destroy(self):
        self._search_cache.clear()
        self._ssl_bad_domains.clear()
        try:
            self._sess.close()
        except Exception:
            pass
        return None

# -*- coding: utf-8 -*-
"""
红果短剧 (hongguo / www.hongguoapp.cn) —— TVBox/FongMi Spider
性能优化与 Bug 修复版（2026-11）：
1. 修复 quick=True 时 limit=60 未传递给 _search_all 的问题，并缩短快搜超时，避免拖慢聚合搜索。
2. 新增搜索结果短时缓存（TTL 60s），解决 suggest 全量接口在本地翻页时重复发请求的问题。
3. 修复 detailContent 提取 @style 背景图时未剥离 background-image:url(...) 导致封面破图的问题。
4. 预编译高频正则 + 配置 HTTPAdapter 连接池复用，降低低配机顶盒/手机端 CPU 与握手开销。
"""
import re
import sys
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import quote
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
    # 预编译常用正则，提升解析速度
    _RE_TID = re.compile(r"/(?:vodshow|vodtype|show/id)/(\d+)")
    _RE_VID = re.compile(r"/(?:voddetail|detail/id)/(\d+)|/id/(\d+)\.html")
    _RE_STYLE_URL = re.compile(r"url\(['\"]?([^'\")]+)['\"]?\)")
    _RE_YEAR = re.compile(r"((?:19|20)\d{2})")
    _RE_PLAYER_JSON = re.compile(r'player_[a-z0-9]+=(\{.*?\})\s*</script>', re.S)
    _RE_M3U8 = re.compile(r'(?:["\']url["\']\s*:\s*["\']|)(https?[^"\'\s\\]+\.m3u8[^"\'\s\\]*)')
    _RE_MP4 = re.compile(r'(?:["\']url["\']\s*:\s*["\']|)(https?[^"\'\s\\]+\.mp4[^"\'\s\\]*)')
    _RE_IFRAME = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)

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
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
            "X-Requested-With": "XMLHttpRequest",
        }

        # 配置连接池复用，减少 TLS 握手耗时
        self._sess = requests.Session()
        adapter = HTTPAdapter(pool_connections=10, pool_maxsize=10, max_retries=0)
        self._sess.mount("http://", adapter)
        self._sess.mount("https://", adapter)
        self._sess.headers.update(self.headers)

        # 搜索结果轻量缓存: { (key, limit): (timestamp, items, total) }
        self._search_cache = {}

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
        return "Just a moment" in head or "challenges.cloudflare.com" in head

    def _fetch(self, url, timeout=12, headers=None, retries=2):
        """带退避重试的 HTML 抓取（兼容手机端 DNS 首次 lookup 偶发 408）。"""
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

        # 兜底直连（排除 Session 连接池异常）
        try:
            r = requests.get(
                url, headers=req_headers, timeout=timeout,
                verify=False, allow_redirects=True
            )
            r.encoding = "utf-8"
            return r.text or last
        except Exception:
            return last

    def _fetch_json(self, url, timeout=10, retries=2, fallback_direct=True):
        """带重试的 JSON 接口抓取；HTTP 非 200 直接放弃，不浪费时间。"""
        attempts = max(1, int(retries or 1))
        for i in range(attempts):
            try:
                r = self._sess.get(
                    url, headers=self._json_headers, timeout=timeout,
                    verify=False, allow_redirects=True
                )
                if r.status_code != 200:
                    return {}
                j = r.json()
                if isinstance(j, dict) and j.get("code") == 1 and isinstance(j.get("list"), list):
                    return j
                return {}
            except Exception:
                if i < attempts - 1:
                    time.sleep(0.6 * (i + 1))

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

    # ---------- ID 解析 ----------
    def _tid(self, href):
        m = self._RE_TID.search(href or "")
        return m.group(1) if m else ""

    def _vid(self, href):
        m = self._RE_VID.search(href or "")
        if not m:
            return ""
        return m.group(1) or m.group(2) or ""

    # ---------- 列表卡片 ----------
    def _cards(self, html):
        out, seen = [], set()
        if not html or self._is_cf(html):
            return out

        tree = None
        try:
            tree = etree.HTML(html)
        except Exception:
            pass

        if tree is not None:
            for a in tree.xpath(
                '//a[contains(@class,"hl-item-thumb") or contains(@href,"/voddetail/") '
                'or contains(@href,"/vod/detail") or contains(@href,"/detail/")]'
            ):
                try:
                    href = a.get("href", "") or ""
                    vid = self._vid(href)
                    if not vid or vid in seen:
                        continue

                    name = (a.get("title", "") or "").strip()
                    pic = (a.get("data-original", "") or a.get("data-src", "") or "").strip()

                    if not pic or not name:
                        img = a.xpath(".//img")
                        if img:
                            if not pic:
                                pic = (
                                    img[0].get("data-original", "")
                                    or img[0].get("data-src", "")
                                    or img[0].get("src", "")
                                    or ""
                                )
                            if not name:
                                name = (img[0].get("alt", "") or img[0].get("title", "") or "").strip()

                    li = a.getparent()
                    if not name and li is not None:
                        t = li.xpath('.//*[contains(@class,"hl-item-title")]//a/text()')
                        if t:
                            name = t[0].strip()

                    if not name:
                        name = "".join(a.xpath("string(.)")).strip().split("\n")[0].strip()
                    if not name:
                        continue

                    seen.add(vid)
                    item = {"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic)}

                    rm = "".join(
                        a.xpath(
                            './/span[contains(@class,"pic-text") or contains(@class,"remark") '
                            'or contains(@class,"state") or contains(@class,"pic-tag") '
                            'or contains(@class,"remarks")]//text()'
                        )
                    ).strip()
                    if not rm and li is not None:
                        rm = "".join(
                            li.xpath('.//*[contains(@class,"remarks") or contains(@class,"pic-text")]//text()')
                        ).strip()
                    if rm:
                        item["vod_remarks"] = rm

                    out.append(item)
                except Exception:
                    continue

        if not out:
            for m in re.finditer(
                r'<a[^>]+href="([^"]*/(?:voddetail|detail)/[^"]*)"[^>]*>(.*?)</a>',
                html, re.S | re.I
            ):
                try:
                    href, inner = m.group(1), m.group(2)
                    vid = self._vid(href)
                    if not vid or vid in seen:
                        continue
                    tm = re.search(r'title="([^"]+)"', m.group(0))
                    name = tm.group(1).strip() if tm else ""
                    pm = re.search(r'(?:data-original|data-src|src)="([^"]+)"', m.group(0) + inner)
                    pic = pm.group(1) if pm else ""
                    if not name:
                        am = re.search(r'(?:alt|title)="([^"]+)"', inner)
                        name = am.group(1).strip() if am else re.sub(r"<.*?>", "", inner).strip().split("\n")[0].strip()
                    if not name:
                        continue
                    seen.add(vid)
                    out.append({"vod_id": vid, "vod_name": name, "vod_pic": self._fix(pic)})
                except Exception:
                    continue
        return out

    # ---------- 主接口 ----------
    def homeContent(self, filter):
        html = self._get(self.host + "/")
        cls = [{"type_id": "51", "type_name": "短剧"}]
        seen_tid = {"51"}
        try:
            tree = etree.HTML(html or "")
            if tree is not None:
                for a in tree.xpath('//a[contains(@href,"/vodshow/") or contains(@href,"/show/id/")]'):
                    tid = self._tid(a.get("href", "") or "")
                    name = "".join(a.xpath(".//text()")).strip()
                    if (
                        tid and tid not in seen_tid and name and len(name) <= 10
                        and not any(x in name for x in ("首页", "播放", "订阅", "RSS"))
                    ):
                        seen_tid.add(tid)
                        cls.append({"type_id": tid, "type_name": name})
        except Exception:
            pass
        return {"class": cls, "list": self._cards(html), "filters": {}}

    def homeVideoContent(self):
        return {"list": self._cards(self._get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid = str(tid or "51")
        url = f"{self.host}/index.php/ajax/data?mid=1&limit=24&tid={quote(tid)}"
        if pg > 1:
            url += f"&page={pg}"

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

        # HTML 兜底
        html, items = "", []
        for u in (
            f"{self.host}/vodshow/{tid}-----------.html",
            f"{self.host}/index.php/vod/show/id/{tid}/page/{pg}.html",
        ):
            html = self._get(u)
            items = self._cards(html)
            if items:
                break

        ms = [int(x) for x in re.findall(r"第\s*(\d+)\s*页", html or "")]
        pc = max(ms + [pg]) if ms else pg
        return {"page": pg, "pagecount": pc, "limit": 24, "total": pc * 24, "list": items}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        result = {"list": []}
        if not vid:
            return result

        urls = [vid] if vid.startswith("http") else [
            f"{self.host}/voddetail/{vid}.html",
            f"{self.host}/index.php/vod/detail/id/{vid}.html",
        ]
        html = ""
        for u in urls:
            html = self._get(u)
            if html and not self._is_cf(html) and "404 Not Found" not in html[:600] and len(html) > 1500:
                break
        if not html or self._is_cf(html):
            return result

        try:
            tree = etree.HTML(html)
        except Exception:
            return result
        if tree is None:
            return result

        name = "".join(tree.xpath('//h2[contains(@class,"hl-dc-title")]//text()')).strip()
        if not name:
            name = "".join(
                tree.xpath(
                    '//h1//text() | //*[contains(@class,"detail-title")]//text() | '
                    '//*[contains(@class,"video-info-title")]//text()'
                )
            ).strip()
        if not name:
            m = re.search(r"<title>([^<]+)</title>", html)
            if m:
                name = re.split(r"[-_|《]", m.group(1))[0].strip("《 ")
        if not name:
            return result

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

        actor = "".join(tree.xpath('//*[contains(@class,"video-info-actor")]//text()')).strip()
        if not actor or actor in ("未知", "内详"):
            actor = "/".join(t.strip() for t in tree.xpath('//li[contains(.,"主演")]//a/text()') if t.strip())
            if not actor:
                actor = self.regStr(r"主演[：:]\s*([^<&\n]+)", html).strip()

        director = "".join(tree.xpath('//*[contains(@class,"video-info-director")]//text()')).strip()
        if not director or director in ("未知", "内详"):
            director = "/".join(t.strip() for t in tree.xpath('//li[contains(.,"导演")]//a/text()') if t.strip())
            if not director:
                director = self.regStr(r"导演[：:]\s*([^<&\n]+)", html).strip()

        year = "".join(tree.xpath('//*[contains(@class,"video-info-year")]//text()')).strip()
        if not year or year in ("未知", "内详"):
            year_raw = "".join(tree.xpath('//li[contains(.,"年份")]//text()')).strip()
            my = self._RE_YEAR.search(year_raw or html)
            year = my.group(1) if my else ""

        area = "".join(tree.xpath('//*[contains(text(),"地区")]/following-sibling::*[1]//text()')).strip()
        if not area or area in ("未知", "内详"):
            area = re.sub(
                r"^地区[：:\s]*", "",
                "".join(tree.xpath('//li[contains(.,"地区")]//text()')).strip()
            ).strip()

        des = re.sub(
            r"^简介[：:\s]*", "",
            "".join(tree.xpath('//li[contains(.,"简介")]//text()')).strip()
        ).strip()
        if not des:
            des = "".join(
                tree.xpath(
                    '//*[contains(@class,"detail-content") or contains(@class,"video-info-content") '
                    'or contains(@class,"vod-content")]//text()'
                )
            ).strip()[:2000]

        eps, seen_ep = [], set()
        for a in tree.xpath('//a[contains(@href,"/vodplay/")]'):
            t = "".join(a.xpath(".//text()")).strip()
            h = self._fix(a.get("href", "") or "")
            if t and h and h not in seen_ep:
                seen_ep.add(h)
                eps.append(f"{t}${h}")

        if not eps:
            for m in re.finditer(r'href="([^"]*/vodplay/[^"]*\.html)"[^>]*>([^<]{1,30})</a>', html):
                h = self._fix(m.group(1))
                if h not in seen_ep:
                    seen_ep.add(h)
                    eps.append(f"{m.group(2).strip()}${h}")

        result["list"].append({
            "vod_id": vid,
            "vod_name": name,
            "vod_pic": self._fix(pic),
            "vod_actor": actor,
            "vod_director": director,
            "vod_year": year,
            "vod_area": area,
            "vod_content": des,
            "vod_play_from": "红果" if eps else "",
            "vod_play_url": "#".join(eps),
        })
        return result

    # ---------- 搜索（含短时缓存与快搜超时控制） ----------
    def _search_all(self, key, limit=200, quick=False):
        clean_key = str(key or "").strip()
        if not clean_key:
            return [], 0

        limit = max(1, min(int(limit or 200), 200))
        cache_key = (clean_key, limit)
        now = time.time()

        # 命中 60 秒内缓存直接返回（翻页零延迟）
        cached = self._search_cache.get(cache_key)
        if cached and (now - cached[0] < 60):
            return cached[1], cached[2]

        # 清理过期缓存，防止内存堆积
        if len(self._search_cache) > 30:
            self._search_cache = {k: v for k, v in self._search_cache.items() if now - v[0] < 60}

        q = quote(clean_key)
        url = f"{self.host}/index.php/ajax/suggest?mid=1&wd={q}&limit={limit}"

        # quick=True 时缩短超时且取消直连兜底，避免聚合搜索卡顿
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

        # 快搜失败直接返回，不走已被 CF 拦截的 HTML 兜底浪费时间
        if is_quick:
            return {"list": [], "page": pg}

        q = quote(str(key or ""))
        for u in (
            f"{self.host}/vodsearch/-------------.html?wd={q}",
            f"{self.host}/index.php/vod/search.html?wd={q}",
        ):
            items = self._cards(self._get(u))
            if items:
                break
        return {"list": items, "page": pg}

    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)

    # ---------- 播放 ----------
    def _playurl(self, html):
        if not html:
            return ""
        for m in self._RE_PLAYER_JSON.finditer(html):
            try:
                obj = json.loads(m.group(1))
                url = (obj.get("url") or "").split(";")[0]
                if isinstance(url, str) and ".m3u8" in url and url.startswith("http"):
                    return url
            except Exception:
                continue

        for rx in (self._RE_M3U8, self._RE_MP4):
            m = rx.search(html)
            if m:
                return m.group(1).replace("\\/", "/")
        return ""

    def playerContent(self, flag, id, vipFlags):
        pid = id or ""
        if pid.startswith("http"):
            page = pid
        elif pid.startswith("/"):
            page = self.host + pid
        else:
            page = f"{self.host}/vodplay/{pid}.html"

        html = self._get(page)
        if self._is_cf(html):
            return {"parse": 1, "url": page}

        url = self._playurl(html)
        if url and (url.startswith("http") or url.startswith("//")):
            return {
                "parse": 0,
                "url": self._fix(url),
                "header": {"User-Agent": self.ua, "Referer": page},
            }

        m = self._RE_IFRAME.search(html or "")
        if m:
            fr = self._fix(m.group(1))
            url = self._playurl(self._get(fr))
            if url:
                return {
                    "parse": 0,
                    "url": self._fix(url),
                    "header": {"User-Agent": self.ua, "Referer": fr},
                }

        return {
            "parse": 1,
            "url": page,
            "header": {"User-Agent": self.ua, "Referer": page},
        }

    def isVideoFormat(self, url):
        u = (url or "").lower()
        return any(ext in u for ext in (".m3u8", ".mp4", ".m4v", ".flv", ".ts", ".webm", ".mov", ".mpd"))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def getDependence(self):
        return []

    def destroy(self):
        self._search_cache.clear()
        try:
            self._sess.close()
        except Exception:
            pass
        return None

# -*- coding: utf-8 -*-
"""
红果短剧 (hongguo / www.hongguoapp.cn) —— TVBox/FongMi Spider
分类筛选与播放 SSL 证书绕过修复版（2026-11）：
1. 修复“没有分类”：该站为纯短剧站（主分类 tid=51），新增短剧题材分类映射与 filters 筛选器，支持按题材翻页。
2. 修复“只抓到立即免费播放”：过滤伪播放按钮，强化海螺(conch)播放列表容器解析，完整提取全集列表。
3. 修复“与媒体服务器的安全连接失败”：内置 SSL 证书快速探测，若媒体服务器 HTTPS 证书异常，自动切换 HTTP 或走 localProxy 绕过证书校验。
"""
import re
import sys
import json
import time
import base64
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import quote, unquote
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
    _RE_M3U8 = re.compile(r'(?:["\']url["\']\s*:\s*["\']|)(https?[^"\'\s\\]+\.m3u8[^"\'\s\\]*)')
    _RE_MP4 = re.compile(r'(?:["\']url["\']\s*:\s*["\']|)(https?[^"\'\s\\]+\.mp4[^"\'\s\\]*)')
    _RE_IFRAME = re.compile(r'<iframe[^>]+src=["\']([^"\']+)["\']', re.I)

    # 纯短剧站虚拟题材分类（通过 ajax/data 的 class 参数筛选）
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
        return "Just a moment" in head or "challenges.cloudflare.com" in head

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

    def _fetch_json(self, url, timeout=10, retries=2, fallback_direct=True):
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

    def _fix_ssl_url(self, url, referer=""):
        """
        针对 ExoPlayer '与媒体服务器的安全连接失败，请检查证书或代理'：
        探测目标 HTTPS 域名的 SSL 证书是否有效；若证书过期/自签导致 SSLError，
        优先尝试降级为 http://，若 http 不通则转交 localProxy 代理流（verify=False）。
        """
        if not url or not url.startswith("https://"):
            return url

        try:
            domain = url.split("/")[2]
        except Exception:
            return url

        is_bad = domain in self._ssl_bad_domains
        if not is_bad:
            try:
                # 严格验证 SSL 证书（verify=True），超时 3 秒
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
                # 非 SSL 错误（如 405 Method Not Allowed 或超时），保持原链接
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
            # 若目标服务器强制 HTTPS 且证书无效，走本地代理剥离 SSL 校验
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

    # ---------- 主接口（修复分类与筛选） ----------
    def homeContent(self, filter):
        html = self._get(self.host + "/")
        cls = []
        seen_tid = set()
        blacklist = ("首页", "播放", "订阅", "RSS", "留言", "求片", "排行", "专题", "APP", "下载")

        try:
            tree = etree.HTML(html or "")
            if tree is not None:
                for a in tree.xpath(
                    '//a[contains(@href,"/vodshow/") or contains(@href,"/vodtype/") '
                    'or contains(@href,"/type/") or contains(@href,"/show/id/")]'
                ):
                    href = a.get("href", "") or ""
                    tid = self._tid(href)
                    name = "".join(a.xpath(".//text()")).strip()
                    if (
                        tid and tid not in seen_tid and name and 1 < len(name) <= 8
                        and not any(x in name for x in blacklist)
                    ):
                        seen_tid.add(tid)
                        cls.append({"type_id": tid, "type_name": name})
        except Exception:
            pass

        # 若站点为纯短剧站（仅提取到 0 或 1 个主分类），启用内置题材分类 Tab
        if len(cls) <= 1:
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

        return {"class": cls, "list": self._cards(html), "filters": filters}

    def homeVideoContent(self):
        return {"list": self._cards(self._get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        extend = extend or {}
        raw_tid = str(tid or "51")

        # 解析虚拟分类 "51:古装" -> tid="51", sub_class="古装"
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

        # HTML 兜底
        html, items = "", []
        candidates = [
            f"{self.host}/vodshow/{real_tid}--------{pg}---.html" if pg > 1 else f"{self.host}/vodshow/{real_tid}-----------.html",
            f"{self.host}/vodtype/{real_tid}-{pg}.html" if pg > 1 else f"{self.host}/vodtype/{real_tid}.html",
            f"{self.host}/index.php/vod/show/id/{real_tid}/page/{pg}.html",
        ]
        for u in candidates:
            html = self._get(u)
            items = self._cards(html)
            if items:
                break

        ms = [int(x) for x in re.findall(r"第\s*(\d+)\s*页", html or "")]
        pc = max(ms + [pg]) if ms else pg
        return {"page": pg, "pagecount": pc, "limit": 24, "total": pc * 24, "list": items}

    # ---------- 详情页（过滤伪按钮、提取完整分集） ----------
    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        result = {"list": []}
        if not vid:
            return result

        urls = [vid] if vid.startswith("http") else [
            f"{self.host}/voddetail/{vid}.html",
            f"{self.host}/index.php/vod/detail/id/{vid}.html",
            f"{self.host}/detail/{vid}.html",
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

        # 优先从正规播放列表容器中提取分集，过滤掉“立即免费播放”等封面大按钮
        eps, seen_ep = [], set()
        fallback_btn = None

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

        # 若整页确实只有一个“立即免费播放”按钮，则作为第1集保底
        if not eps and fallback_btn:
            eps.append(f"第1集${fallback_btn[1]}")

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

    # ---------- 播放（SSL 证书绕过与解密） ----------
    def _decode_player_url(self, raw_url, encrypt):
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

    def _playurl(self, html):
        if not html:
            return ""
        for m in self._RE_PLAYER_JSON.finditer(html):
            try:
                obj = json.loads(m.group(1))
                raw_url = (obj.get("url") or "").split(";")[0]
                url = self._decode_player_url(raw_url, obj.get("encrypt", 0))
                if url and (url.startswith("http") or url.startswith("//")):
                    return url
            except Exception:
                continue

        for rx in (self._RE_M3U8, self._RE_MP4):
            m = rx.search(html)
            if m:
                return unquote(m.group(1).replace("\\/", "/"))
        return ""

    def playerContent(self, flag, id, vipFlags):
        pid = str(id or "").strip()
        if pid.startswith("http"):
            page = pid
        elif pid.startswith("/"):
            page = self.host + pid
        else:
            page = f"{self.host}/vodplay/{pid}.html"

        if self.isVideoFormat(page):
            safe_url = self._fix_ssl_url(self._fix(page), self.host + "/")
            return {
                "parse": 0,
                "url": safe_url,
                "header": {"User-Agent": self.ua, "Referer": self.host + "/"},
            }

        html = self._get(page)
        if self._is_cf(html):
            return {"parse": 1, "url": self._fix_ssl_url(page, page)}

        url = self._playurl(html)
        if url and (url.startswith("http") or url.startswith("//")):
            fixed_url = self._fix(url)
            is_direct = self.isVideoFormat(fixed_url)
            safe_url = self._fix_ssl_url(fixed_url, page)
            return {
                "parse": 0 if is_direct else 1,
                "url": safe_url,
                "header": {"User-Agent": self.ua, "Referer": page},
            }

        m = self._RE_IFRAME.search(html or "")
        if m:
            fr = self._fix(m.group(1))
            fr_html = self._get(fr)
            url = self._playurl(fr_html)
            if url:
                fixed_url = self._fix(url)
                safe_url = self._fix_ssl_url(fixed_url, fr)
                return {
                    "parse": 0 if self.isVideoFormat(fixed_url) else 1,
                    "url": safe_url,
                    "header": {"User-Agent": self.ua, "Referer": fr},
                }

        return {
            "parse": 1,
            "url": self._fix_ssl_url(page, page),
            "header": {"User-Agent": self.ua, "Referer": page},
        }

    def localProxy(self, param):
        """当媒体服务器 SSL 证书无效且不支持纯 HTTP 时，由本地代理忽略证书转发媒体流/M3U8。"""
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
            # 如果是 m3u8 索引文件，重写里面的相对路径或坏 SSL 的 https 链接
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
        u = (url or "").lower().split("?")[0]
        return any(u.endswith(ext) or (ext in u) for ext in (".m3u8", ".mp4", ".m4v", ".flv", ".ts", ".webm", ".mov", ".mpd"))

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

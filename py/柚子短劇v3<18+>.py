# -*- coding: utf-8 -*-
"""
柚子短剧 (youzidj / https://youzidj.com) —— TVBox/FongMi/修狗TV Python Spider
"""
import re
import sys
import json
import time
import base64
import threading
import requests
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import quote, unquote, urljoin, urlparse, parse_qs
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

    def getName(self):
        return "柚子短剧_v3"

    def init(self, extend=""):
        self.host = "https://youzidj.com"
        self.hosts = ["https://youzidj.com"]
        try:
            o = json.loads(extend) if extend else {}
            if isinstance(o, dict) and o.get("host"):
                self.host = o["host"].rstrip("/")
                self.hosts = [self.host] + [h for h in self.hosts if h != self.host]
        except Exception:
            pass

        self.ua = (
            "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
        )
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8",
            "Referer": self.host + "/",
        }
        self._sess = requests.Session()
        try:
            self._sess.headers.update(self.headers)
        except Exception:
            pass

        self._httpd = None
        self._proxy_port = 0
        self._start_local_server()

    # ---------- 独立本地 HTTP 代理服务器（兼容明文查询串与 Base64 路径参数） ----------
    def _start_local_server(self):
        spider_ref = self

        class ProxyHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                parsed = urlparse(self.path)
                target_url = ""
                ref = spider_ref.host + "/"

                # 1. 解析明文查询参数 ?url=...&ref=...
                if parsed.query:
                    qs = parse_qs(parsed.query)
                    if qs.get("url"):
                        target_url = unquote(qs["url"][0])
                    if qs.get("ref"):
                        ref = unquote(qs["ref"][0])

                # 2. 解析修狗TV自动转换的 /proxy/<base64> 路径参数
                if not target_url and parsed.path.startswith("/proxy/"):
                    b64_part = parsed.path[len("/proxy/"):].strip("/")
                    try:
                        pad = "=" * ((4 - len(b64_part) % 4) % 4)
                        decoded_qs = base64.urlsafe_b64decode(
                            (b64_part + pad).encode("ascii")
                        ).decode("utf-8", errors="ignore")
                        qs = parse_qs(decoded_qs)
                        if qs.get("url"):
                            target_url = unquote(qs["url"][0])
                        if qs.get("ref"):
                            ref = unquote(qs["ref"][0])
                    except Exception:
                        pass

                if not target_url:
                    msg = f"bad proxy path: {self.path}".encode("utf-8")
                    self.send_response(400)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(msg)))
                    self.end_headers()
                    self.wfile.write(msg)
                    return

                req_headers = {
                    "User-Agent": spider_ref.ua,
                    "Referer": ref,
                    "Origin": spider_ref.host,
                    "Accept": "*/*",
                    "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8",
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                }
                try:
                    r = spider_ref._sess.get(
                        target_url, headers=req_headers, timeout=15, verify=False
                    )
                    if r.status_code == 403:
                        spider_ref._get(ref)
                        r = spider_ref._sess.get(
                            target_url, headers=req_headers, timeout=15, verify=False
                        )

                    ctype = r.headers.get("Content-Type", "application/octet-stream")
                    if ".m3u8" in target_url.lower() or "mpegurl" in ctype.lower():
                        r.encoding = "utf-8"
                        base_proxy = f"http://127.0.0.1:{spider_ref._proxy_port}/proxy"
                        lines = []
                        for line in r.text.splitlines():
                            s = line.strip()
                            if s and not s.startswith("#"):
                                abs_u = urljoin(target_url, s)
                                lines.append(
                                    f"{base_proxy}?url={quote(abs_u)}&ref={quote(ref)}"
                                )
                            elif 'URI="' in s:
                                def _rep_uri(m):
                                    abs_u = urljoin(target_url, m.group(1))
                                    return f'URI="{base_proxy}?url={quote(abs_u)}&ref={quote(ref)}"'
                                lines.append(re.sub(r'URI="([^"]+)"', _rep_uri, s))
                            else:
                                lines.append(line)

                        body = "\n".join(lines).encode("utf-8")
                        self.send_response(200)
                        self.send_header("Content-Type", "application/vnd.apple.mpegurl; charset=utf-8")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                    else:
                        body = r.content
                        self.send_response(r.status_code)
                        self.send_header("Content-Type", ctype)
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                except Exception as e:
                    err = str(e).encode("utf-8", errors="ignore")
                    self.send_response(502)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Content-Length", str(len(err)))
                    self.end_headers()
                    self.wfile.write(err)

        try:
            server = HTTPServer(("127.0.0.1", 0), ProxyHandler)
            self._httpd = server
            self._proxy_port = server.server_address[1]
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
        except Exception:
            self._httpd = None
            self._proxy_port = 0

    # ---------- 基础工具 ----------
    def _fix(self, u):
        if not u:
            return ""
        u = str(u).strip().replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")
        if u.startswith("data:"):
            return ""
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        if not u.startswith("http"):
            return urljoin(self.host + "/", u)
        return u

    def _path(self, u):
        if not u:
            return ""
        u = str(u).strip()
        for h in self.hosts:
            if u.startswith(h):
                u = u[len(h):]
                break
        if u.startswith("/zh-hant/"):
            u = u[len("/zh-hant"):]
        return u if u.startswith("/") else "/" + u

    def _is_cf(self, html):
        if not html:
            return False
        head = html[:4000]
        return ("Just a moment" in head or "challenges.cloudflare.com" in head
                or "cf-browser-verification" in head)

    def _fetch(self, url, timeout=15, headers=None, retries=3, min_len=1500):
        last = ""
        req_headers = headers or self.headers
        for i in range(max(1, int(retries or 1))):
            try:
                r = self._sess.get(url, headers=req_headers, timeout=timeout,
                                   verify=False, allow_redirects=True)
                r.encoding = "utf-8"
                last = r.text or ""
                if last and (len(last) >= min_len or self._is_cf(last) or r.status_code == 404):
                    return last
            except Exception:
                last = last or ""
            if i < int(retries or 1) - 1:
                try:
                    time.sleep(0.6 * (i + 1))
                except Exception:
                    pass
        if last and len(last) >= min_len:
            return last
        try:
            r = requests.get(url, headers=req_headers, timeout=timeout,
                             verify=False, allow_redirects=True)
            r.encoding = "utf-8"
            return r.text or last
        except Exception:
            return last

    def _get(self, url, min_len=1500):
        html = self._fetch(url, min_len=min_len)
        if html and len(html) >= min_len and not self._is_cf(html):
            return html
        for h in self.hosts:
            if h == self.host:
                continue
            try:
                t = self._fetch(url.replace(self.host, h, 1), timeout=8, min_len=min_len)
                if t and len(t) >= min_len and not self._is_cf(t) and "404 Not Found" not in t[:600]:
                    self.host = h
                    self.headers["Referer"] = h + "/"
                    return t
            except Exception:
                continue
        return html

    # ---------- 卡片解析 ----------
    def _cards(self, html):
        out, seen = [], set()
        if not html or self._is_cf(html):
            return out
        try:
            tree = etree.HTML(html)
        except Exception:
            tree = None

        if tree is not None:
            cards = tree.xpath('//article[contains(@class,"drama-card")]')
            for card in cards:
                try:
                    a_list = card.xpath('.//a[contains(@class,"home-drama-card-link") or @href][1]')
                    if not a_list:
                        continue
                    a = a_list[0]
                    href = a.get("href", "") or ""
                    vid = self._path(href)
                    if not vid or vid == "/" or vid in seen:
                        continue

                    name = "".join(card.xpath('.//*[contains(@class,"drama-card-title")]//text()')).strip()
                    if not name:
                        name = (a.get("aria-label", "") or "").replace("查看详情：", "").strip()
                    if not name:
                        img_alt = card.xpath('.//img/@alt')
                        if img_alt:
                            name = re.sub(r"海报$", "", img_alt[0]).strip()
                    if not name:
                        continue

                    pic = ""
                    for xp in ['.//img/@data-image-src', './/img/@src', './/img/@data-src', './/img/@data-original']:
                        vals = card.xpath(xp)
                        for v in vals:
                            fixed = self._fix(v)
                            if fixed:
                                pic = fixed
                                break
                        if pic:
                            break

                    rm = "".join(card.xpath('.//*[contains(@class,"home-card-episodes-long")]//text()')).strip()
                    if not rm:
                        rm = "".join(card.xpath('.//*[contains(@class,"home-card-episodes")]//text()')).strip()
                    badge = "".join(card.xpath('.//*[contains(@class,"home-card-badge")]//text()')).strip()
                    if badge and rm:
                        rm = f"[{badge}] {rm}"

                    seen.add(vid)
                    item = {"vod_id": vid, "vod_name": name, "vod_pic": pic}
                    if rm:
                        item["vod_remarks"] = rm
                    out.append(item)
                except Exception:
                    continue

            if not out:
                for a in tree.xpath('//a[contains(@href,"/dramas/") or contains(@href,"/ai-face-swap/") or contains(@href,"/ai-adult/")]'):
                    try:
                        href = a.get("href", "") or ""
                        vid = self._path(href)
                        if vid.rstrip("/") in ("/dramas", "/ai-face-swap", "/ai-adult") or vid in seen:
                            continue
                        name = (a.get("title", "") or a.get("aria-label", "") or "").replace("查看详情：", "").strip()
                        if not name:
                            name = "".join(a.xpath('.//text()')).strip()
                        if not name or len(name) > 60:
                            continue
                        pic = ""
                        imgs = a.xpath('.//img/@data-image-src | .//img/@src')
                        for v in imgs:
                            pic = self._fix(v)
                            if pic:
                                break
                        seen.add(vid)
                        out.append({"vod_id": vid, "vod_name": name, "vod_pic": pic})
                    except Exception:
                        continue
        return out

    # ---------- TVBox 主接口 ----------
    def homeContent(self, filter):
        html = self._get(self.host + "/")
        cls = [
            {"type_id": "/dramas/", "type_name": "AI短剧"},
            {"type_id": "/ai-face-swap/", "type_name": "AI换脸"},
            {"type_id": "/ai-adult/", "type_name": "AI成人视频"},
            {"type_id": "/tags/romance/", "type_name": "情感"},
            {"type_id": "/tags/shu-nu/", "type_name": "熟女"},
            {"type_id": "/tags/ren-qi/", "type_name": "人妻"},
            {"type_id": "/tags/tou-qing/", "type_name": "偷情"},
            {"type_id": "/tags/yu-jie/", "type_name": "御姐"},
            {"type_id": "/tags/ming-xing/", "type_name": "明星"},
        ]
        try:
            tree = etree.HTML(html or "")
            if tree is not None:
                for a in tree.xpath('//a[contains(@href,"/tags/")]'):
                    tid = self._path(a.get("href", ""))
                    name = "".join(a.xpath('.//text()')).strip()
                    if tid and name and len(name) <= 8 and all(c["type_id"] != tid for c in cls):
                        cls.append({"type_id": tid, "type_name": name})
                        if len(cls) >= 18:
                            break
        except Exception:
            pass

        return {"class": cls, "list": self._cards(html), "filters": {}}

    def homeVideoContent(self):
        return {"list": self._cards(self._get(self.host + "/"))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        tid_path = self._path(tid or "/dramas/")
        if not tid_path.endswith("/"):
            tid_path += "/"

        url = self.host + tid_path + (f"?page={pg}" if pg > 1 else "")
        html = self._get(url)
        items = self._cards(html)

        if not items and pg > 1:
            parts = [p for p in tid_path.strip("/").split("/") if p]
            if len(parts) == 1:
                api_url = f"{self.host}/api/catalogue/browse?section={quote(parts[0])}&page={pg}"
            else:
                api_url = f"{self.host}/api/catalogue/browse?tag={quote(parts[-1])}&page={pg}"
            frag = self._get(api_url, min_len=200)
            items = self._cards(frag)

        pagecount = pg + 1 if len(items) >= 12 else pg
        return {
            "page": pg,
            "pagecount": pagecount,
            "limit": 24,
            "total": pagecount * 24,
            "list": items,
        }

    def detailContent(self, ids):
        raw_id = str(ids[0]) if ids else ""
        result = {"list": []}
        if not raw_id:
            return result

        page_url = self._fix(raw_id)
        html = self._get(page_url)
        if not html or self._is_cf(html):
            return result

        try:
            tree = etree.HTML(html)
        except Exception:
            return result
        if tree is None:
            return result

        name = "".join(tree.xpath('//h1[contains(@class,"p-watch-heading")]//text()')).strip()
        if not name:
            name = "".join(tree.xpath('//h1//text()')).strip()
        name = re.sub(r"\s*·\s*第\s*\d+\s*季.*$", "", name).strip()
        if not name:
            m = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            if m:
                name = re.split(r"[第|｜]", m.group(1))[0].strip()
        if not name:
            return result

        pic = ""
        for xp in [
            '//a[contains(@class,"watch-title-cover")]//img/@data-image-src',
            '//a[contains(@class,"watch-title-cover")]//img/@src',
            '//meta[@property="og:image"]/@content',
            '//img[contains(@class,"privacy-cover")]/@src',
        ]:
            vals = tree.xpath(xp)
            for v in vals:
                fixed = self._fix(v)
                if fixed:
                    pic = fixed
                    break
            if pic:
                break

        tags = [t.strip() for t in tree.xpath('//*[contains(@class,"p-watch-tags")]//a/text()') if t.strip()]
        vtype = " / ".join(tags) if tags else "AI短剧"

        des = "".join(tree.xpath('//*[contains(@class,"watch-episode-synopsis")]//p//text()')).strip()
        if not des:
            m = re.search(r'<meta name="description" content="([^"]+)"', html)
            if m:
                des = m.group(1).strip()

        eps = []
        seen_ep = set()
        for a in tree.xpath('//a[contains(@class,"series-episode-link")]'):
            try:
                href = self._fix(a.get("href", "") or "")
                if not href or href in seen_ep:
                    continue
                ep_num = "".join(a.xpath('.//text()')).strip()
                ep_title = (a.get("title", "") or "").strip()
                label = f"第{ep_num}集" if ep_num.isdigit() else (ep_num or ep_title)
                if ep_title and len(ep_title) <= 22:
                    label = f"{label} {ep_title}"
                seen_ep.add(href)
                eps.append(f"{label}${href}")
            except Exception:
                continue

        if not eps:
            eps.append(f"正片${page_url}")

        vod = {
            "vod_id": self._path(page_url),
            "vod_name": name,
            "vod_pic": pic,
            "type_name": vtype,
            "vod_area": "国产",
            "vod_remarks": f"共{len(eps)}集",
            "vod_content": des,
            "vod_play_from": "柚子短剧",
            "vod_play_url": "#".join(eps),
        }
        result["list"].append(vod)
        return result

    # ---------- 搜索接口 ----------
    def searchContent(self, key, quick, pg="1"):
        pg = int(pg or 1)
        kw = str(key or "").strip()
        if not kw:
            return {"list": [], "page": pg}

        q = quote(kw)
        items = []

        if pg == 1:
            html = self._get(f"{self.host}/search/?q={q}")
            items = self._cards(html)

        if not items or pg > 1:
            seen = {it["vod_id"] for it in items}
            for kind in ("dramas", "videos"):
                api_url = f"{self.host}/api/catalogue/search?q={q}&kind={kind}&page={pg}"
                frag = self._get(api_url, min_len=150)
                for it in self._cards(frag):
                    if it["vod_id"] not in seen:
                        seen.add(it["vod_id"])
                        items.append(it)

        return {
            "list": items,
            "page": pg,
            "pagecount": pg + 1 if len(items) >= 10 else pg,
            "limit": 24,
            "total": len(items),
        }

    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)

    # ---------- 直链提取与本地代理播放 ----------
    def _extract_m3u8(self, html):
        if not html:
            return ""
        clean_html = html.replace("\\/", "/").replace("\\u002F", "/").replace("\\u002f", "/")

        for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', clean_html, re.S | re.I):
            try:
                data = json.loads(m.group(1).strip())
                items = data if isinstance(data, list) else [data]
                for obj in items:
                    if isinstance(obj, dict):
                        cu = obj.get("contentUrl") or obj.get("embedUrl") or ""
                        if isinstance(cu, str) and (".m3u8" in cu or ".mp4" in cu):
                            return self._fix(cu)
            except Exception:
                continue

        for pat in [
            r'"(?:contentUrl|videoUrl|playUrl|url|src)"\s*:\s*"([^"]+\.(?:m3u8|mp4)[^"]*)"',
            r'<source[^>]+src=["\']([^"\']+\.(?:m3u8|mp4)[^"\']*)["\']',
            r'(https?://[^"\'\s<>\\]+\.m3u8[^"\'\s<>\\]*)',
            r'(/media/[a-zA-Z0-9-]+/[a-zA-Z0-9-]+/master\.m3u8[^"\'\s<>\\]*)',
            r'"contentUrl"\s*:\s*"([^"]+\.mp4[^"]*)"',
            r'(https?://[^"\'\s<>\\]+\.mp4[^"\'\s<>\\]*)',
        ]:
            m = re.search(pat, clean_html, re.I)
            if m:
                return self._fix(m.group(1))
        return ""

    def playerContent(self, flag, id, vipFlags):
        page_url = self._fix(id or "")
        if not page_url:
            return {"parse": 1, "jx": 0, "url": ""}

        if not self._sess.cookies.get_dict():
            self._get(self.host + "/")
        html = self._get(page_url)

        stream_url = page_url if self.isVideoFormat(page_url) else self._extract_m3u8(html)

        if stream_url:
            if not self._proxy_port:
                self._start_local_server()
            if self._proxy_port:
                proxy_url = f"http://127.0.0.1:{self._proxy_port}/proxy?url={quote(stream_url)}&ref={quote(page_url)}"
                return {
                    "parse": 0,
                    "jx": 0,
                    "url": proxy_url,
                }
            return {
                "parse": 0,
                "jx": 0,
                "url": stream_url,
                "header": {"User-Agent": self.ua, "Referer": page_url},
            }

        return {
            "parse": 1,
            "jx": 0,
            "url": page_url,
            "header": {"User-Agent": self.ua, "Referer": page_url},
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
        try:
            if self._httpd:
                self._httpd.shutdown()
                self._httpd.server_close()
        except Exception:
            pass
        try:
            self._sess.close()
        except Exception:
            pass
        return None

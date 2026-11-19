# -*- coding: utf-8 -*-
"""
柚子短剧 (youzidj / https://youzidj.com) —— TVBox/FongMi/修狗TV Python Spider
特性：
1. 适配站内 SSR HTML + /api/catalogue/search（HTML片段）双重解析
2. 搜索支持首页直出（/search/?q=）与多类型（dramas/videos）无限翻页加载
3. 详情页直接提取全季所有分集（a.series-episode-link）
4. 通过播放器内置 localProxy 代理转发 master.m3u8 与 ts 切片，自动注入 Session Cookie、Origin 与 Referer 解决 403 Forbidden
5. 针对弱网/DNS 抖动内置指数退避重试与 Session/直连自动降级
"""
import re
import sys
import json
import time
import base64
import requests
from urllib.parse import quote, unquote, urljoin, parse_qs
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
        return "柚子短剧"

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

    # ---------- 直链提取与内置 localProxy 代理播放 ----------
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

    def _build_proxy_url(self, stream_url, page_url):
        # 将 url 与 ref 打包为一个安全的 URL 参数，避免多参数在部分壳子中丢失
        payload = json.dumps({"u": stream_url, "r": page_url}, separators=(",", ":"))
        b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
        try:
            pbase = self.getProxyUrl()
            if pbase:
                sep = "&" if "?" in pbase else "?"
                return f"{pbase}{sep}p={b64}"
        except Exception:
            pass
        return f"http://127.0.0.1:9978/proxy?do=py&p={b64}"

    def playerContent(self, flag, id, vipFlags):
        page_url = self._fix(id or "")
        if not page_url:
            return {"parse": 1, "jx": 0, "url": ""}

        if not self._sess.cookies.get_dict():
            self._get(self.host + "/")
        html = self._get(page_url)

        stream_url = page_url if self.isVideoFormat(page_url) else self._extract_m3u8(html)
        if stream_url:
            return {
                "parse": 0,
                "jx": 0,
                "url": self._build_proxy_url(stream_url, page_url),
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
        if not isinstance(param, dict):
            param = {}

        target_url = ""
        ref = self.host + "/"

        # 1. 优先解析打包的 p 参数
        p_val = param.get("p", "")
        if p_val:
            try:
                pad = "=" * ((4 - len(p_val) % 4) % 4)
                raw = base64.urlsafe_b64decode((p_val + pad).encode("ascii")).decode("utf-8")
                obj = json.loads(raw)
                target_url = obj.get("u", "")
                ref = obj.get("r", ref)
            except Exception:
                pass

        # 2. 兼容直接传递的 url/ref 参数或 path 末尾的 base64 查询串
        if not target_url and param.get("url"):
            target_url = unquote(str(param.get("url")))
            ref = unquote(str(param.get("ref", ref)))

        if not target_url:
            for k, v in param.items():
                if isinstance(v, str) and "url=" in v:
                    qs = parse_qs(v)
                    if qs.get("url"):
                        target_url = unquote(qs["url"][0])
                        if qs.get("ref"):
                            ref = unquote(qs["ref"][0])
                        break

        if not target_url:
            return [404, "text/plain", b"missing target_url"]

        headers = {
            "User-Agent": self.ua,
            "Referer": ref,
            "Origin": self.host,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        try:
            r = self._sess.get(target_url, headers=headers, timeout=15, verify=False)
            if r.status_code == 403:
                self._get(ref)
                r = self._sess.get(target_url, headers=headers, timeout=15, verify=False)

            ctype = r.headers.get("Content-Type", "application/octet-stream")
            if ".m3u8" in target_url.lower() or "mpegurl" in ctype.lower():
                r.encoding = "utf-8"
                lines = []
                for line in r.text.splitlines():
                    s = line.strip()
                    if s and not s.startswith("#"):
                        abs_u = urljoin(target_url, s)
                        lines.append(self._build_proxy_url(abs_u, ref))
                    elif 'URI="' in s:
                        def _rep_uri(m):
                            abs_u = urljoin(target_url, m.group(1))
                            return f'URI="{self._build_proxy_url(abs_u, ref)}"'
                        lines.append(re.sub(r'URI="([^"]+)"', _rep_uri, s))
                    else:
                        lines.append(line)
                return [200, "application/vnd.apple.mpegurl", "\n".join(lines).encode("utf-8")]

            return [r.status_code, ctype, r.content]
        except Exception as e:
            return [502, "text/plain", str(e).encode("utf-8")]

    def getDependence(self):
        return []

    def destroy(self):
        try:
            self._sess.close()
        except Exception:
            pass
        return None

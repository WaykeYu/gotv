# -*- coding: utf-8 -*-
"""
柚子短剧 (youzidj / https://youzidj.com) —— TVBox/FongMi Python Spider
特性：
  1. 全站 SSR HTML + Catalogue JSON API 双重兼容解析
  2. 详请页直接提取全季所有分集（a.series-episode-link）
  3. 播放页直接从 Schema.org JSON-LD 提取 master.m3u8（parse=0 免嗅探硬解秒播）
  4. 针对弱网/DNS 抖动内置指数退避重试与 Session/直连自动降级
"""
import re
import sys
import json
import time
import requests
from urllib.parse import quote, urljoin
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
        self._json_headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
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
        u = str(u).strip().replace("\\/", "/")
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
        """将完整 URL 标准化为站内相对路径（如 /dramas/xxx/season-1/）"""
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

    def _fetch(self, url, timeout=15, headers=None, retries=3):
        last = ""
        req_headers = headers or self.headers
        for i in range(max(1, int(retries or 1))):
            try:
                r = self._sess.get(url, headers=req_headers, timeout=timeout,
                                   verify=False, allow_redirects=True)
                r.encoding = "utf-8"
                last = r.text or ""
                if last and (len(last) > 1500 or self._is_cf(last) or r.status_code == 404):
                    return last
            except Exception:
                last = last or ""
            if i < int(retries or 1) - 1:
                try:
                    time.sleep(0.6 * (i + 1))
                except Exception:
                    pass
        if last and len(last) > 1500:
            return last
        try:
            r = requests.get(url, headers=req_headers, timeout=timeout,
                             verify=False, allow_redirects=True)
            r.encoding = "utf-8"
            return r.text or last
        except Exception:
            return last

    def _fetch_json(self, url, timeout=12, retries=3):
        for i in range(max(1, int(retries or 1))):
            try:
                r = self._sess.get(url, headers=self._json_headers, timeout=timeout,
                                   verify=False, allow_redirects=True)
                if r.status_code != 200:
                    return {}
                j = r.json()
                if isinstance(j, (dict, list)):
                    return j
                return {}
            except Exception:
                if i < int(retries or 1) - 1:
                    try:
                        time.sleep(0.7 * (i + 1))
                    except Exception:
                        pass
        try:
            r = requests.get(url, headers=self._json_headers, timeout=timeout,
                             verify=False, allow_redirects=True)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return {}

    def _get(self, url):
        html = self._fetch(url)
        if html and len(html) > 1500 and not self._is_cf(html):
            return html
        for h in self.hosts:
            if h == self.host:
                continue
            try:
                t = self._fetch(url.replace(self.host, h, 1), timeout=8)
                if t and len(t) > 1500 and not self._is_cf(t) and "404 Not Found" not in t[:600]:
                    self.host = h
                    self.headers["Referer"] = h + "/"
                    self._json_headers["Referer"] = h + "/"
                    return t
            except Exception:
                continue
        return html

    # ---------- 卡片解析（适配 article.drama-card 结构） ----------
    def _cards(self, html):
        out, seen = [], set()
        if not html or self._is_cf(html):
            return out
        try:
            tree = etree.HTML(html)
        except Exception:
            tree = None

        if tree is not None:
            # 1. 优先匹配标准剧集卡片 article.drama-card
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

                    # 剧名
                    name = "".join(card.xpath('.//*[contains(@class,"drama-card-title")]//text()')).strip()
                    if not name:
                        name = (a.get("aria-label", "") or "").replace("查看详情：", "").strip()
                    if not name:
                        img_alt = card.xpath('.//img/@alt')
                        if img_alt:
                            name = re.sub(r"海报$", "", img_alt[0]).strip()
                    if not name:
                        continue

                    # 封面图（注意跳过 data:image/svg 占位图，优先取真实 src 或 data-image-src）
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

                    # 更新集数备注（如 "更新至5集" / "至5集"）
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

            # 2. 兜底匹配任意指向 /dramas/ 或 /ai-face-swap/ 或 /ai-adult/ 的卡片链接
            if not out:
                for a in tree.xpath('//a[contains(@href,"/dramas/") or contains(@href,"/ai-face-swap/") or contains(@href,"/ai-adult/")]'):
                    try:
                        href = a.get("href", "") or ""
                        vid = self._path(href)
                        # 排除纯目录页，保留具体作品页
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

    def _parse_json_items(self, data):
        """解析 /api/catalogue/... 返回的 JSON 列表（兼容多种常见字段命名）"""
        items = []
        raw_list = []
        if isinstance(data, list):
            raw_list = data
        elif isinstance(data, dict):
            for k in ("items", "list", "results", "data", "works", "dramas"):
                if isinstance(data.get(k), list):
                    raw_list = data[k]
                    break
        for it in raw_list:
            if not isinstance(it, dict):
                continue
            try:
                slug = it.get("url") or it.get("path") or it.get("href") or ""
                if not slug and it.get("slug"):
                    section = it.get("section") or it.get("category") or "dramas"
                    slug = f"/{section}/{it['slug']}/season-1/"
                vid = self._path(slug)
                name = str(it.get("title") or it.get("name") or it.get("vod_name") or "").strip()
                if not vid or vid == "/" or not name:
                    continue
                pic = self._fix(it.get("cover") or it.get("poster") or it.get("image") or it.get("pic") or "")
                ep_cnt = it.get("episodeCount") or it.get("episodes_count") or it.get("episodes")
                rm = str(it.get("remarks") or (f"更新至{ep_cnt}集" if ep_cnt else "")).strip()
                item = {"vod_id": vid, "vod_name": name, "vod_pic": pic}
                if rm:
                    item["vod_remarks"] = rm
                items.append(item)
            except Exception:
                continue
        return items

    # ---------- TVBox 主接口 ----------
    def homeContent(self, filter):
        html = self._get(self.host + "/")
        # 站点主导航分类
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
        # 动态补充首页出现的其他热门标签
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

        # 1. 尝试直接访问 SSR 分类页（支持 ?page=N 翻页）
        url = self.host + tid_path + (f"?page={pg}" if pg > 1 else "")
        html = self._get(url)
        items = self._cards(html)

        # 2. 若第 2 页起 HTML 未返回新数据，尝试调用前端 catalogue browse API
        if not items and pg > 1:
            section = tid_path.strip("/").split("/")[-1]
            api_url = f"{self.host}/api/catalogue/browse?section={quote(section)}&page={pg}&limit=24"
            j = self._fetch_json(api_url)
            items = self._parse_json_items(j)

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

        # 提取剧名（去除 " · 第1季 · 第1集" 后缀）
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

        # 提取海报
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

        # 提取标签作为类型/演员展示
        tags = [t.strip() for t in tree.xpath('//*[contains(@class,"p-watch-tags")]//a/text()') if t.strip()]
        vtype = " / ".join(tags) if tags else "AI短剧"

        # 提取简介
        des = "".join(tree.xpath('//*[contains(@class,"watch-episode-synopsis")]//p//text()')).strip()
        if not des:
            m = re.search(r'<meta name="description" content="([^"]+)"', html)
            if m:
                des = m.group(1).strip()

        # 提取全部分集列表（a.series-episode-link）
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

        # 若当前是单集/单部视频无分集列表，则将当前页面本身作为播放项
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

        # 1. 优先尝试站内 JSON 搜索接口 /api/catalogue/search
        for param in ("q", "wd", "query"):
            j = self._fetch_json(f"{self.host}/api/catalogue/search?{param}={q}&page={pg}&limit=24")
            items = self._parse_json_items(j)
            if items:
                break

        # 2. 兜底请求 SSR 搜索页面 /search/?q=
        if not items:
            for u in [
                f"{self.host}/search/?q={q}" + (f"&page={pg}" if pg > 1 else ""),
                f"{self.host}/search/?wd={q}" + (f"&page={pg}" if pg > 1 else ""),
            ]:
                html = self._get(u)
                items = self._cards(html)
                if items:
                    break

        return {
            "list": items,
            "page": pg,
            "pagecount": pg + 1 if len(items) >= 12 else pg,
            "limit": 24,
            "total": len(items),
        }

    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)

    # ---------- 免 WebView 直链播放解析 ----------
    def _extract_m3u8(self, html):
        if not html:
            return ""
        # 1. 优先从 <script type="application/ld+json"> 的 VideoObject 提取 contentUrl
        for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.S | re.I):
            try:
                data = json.loads(m.group(1).strip())
                if isinstance(data, dict):
                    cu = data.get("contentUrl") or ""
                    if isinstance(cu, str) and (".m3u8" in cu or ".mp4" in cu):
                        return self._fix(cu)
            except Exception:
                continue

        # 2. 正则兜底提取页面内嵌的 master.m3u8 或 mp4 链接
        for pat in [
            r'"contentUrl"\s*:\s*"([^"]+\.m3u8[^"]*)"',
            r'(https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*)',
            r'(/media/[a-zA-Z0-9-]+/[a-zA-Z0-9-]+/master\.m3u8[^"\'\s<>]*)',
            r'"contentUrl"\s*:\s*"([^"]+\.mp4[^"]*)"',
            r'(https?://[^"\'\s<>]+\.mp4[^"\'\s<>]*)',
        ]:
            m = re.search(pat, html)
            if m:
                return self._fix(m.group(1))
        return ""

    def playerContent(self, flag, id, vipFlags):
        page_url = self._fix(id or "")
        if not page_url:
            return {"parse": 1, "url": ""}

        # 如果传入的已经是直链，直接返回
        if self.isVideoFormat(page_url):
            return {
                "parse": 0,
                "url": page_url,
                "header": {"User-Agent": self.ua, "Referer": self.host + "/"},
            }

        html = self._get(page_url)
        if self._is_cf(html):
            return {"parse": 1, "url": page_url}

        stream_url = self._extract_m3u8(html)
        if stream_url:
            return {
                "parse": 0,
                "url": stream_url,
                "header": {
                    "User-Agent": self.ua,
                    "Referer": page_url,
                },
            }

        return {
            "parse": 1,
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
            self._sess.close()
        except Exception:
            pass
        return None

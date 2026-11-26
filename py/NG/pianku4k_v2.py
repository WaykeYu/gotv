# -*- coding: utf-8 -*-
import json
import re
import struct
import sys
import time
import zlib
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, unquote, urlparse
from lxml import etree

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

sys.path.append("..")
from base.spider import Spider


class Spider(Spider):
    # 預編譯常用正則，避免重複編譯開銷
    RE_VOD_ID = re.compile(r"/voddetail/(\d+)\.html")
    RE_PLAYER_DATA = re.compile(r"var\s+player_aaaa\s*=\s*(\{.+?\})\s*;", re.S)
    RE_VIDEO_EXT = re.compile(r"\.(?:m3u8|mp4|flv|mkv|webm)(?:\?|$)", re.I)
    RE_M3U8_URL = re.compile(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', re.I)
    RE_PLINE = re.compile(r'data-prefix="([^"]+)"\s+data-name="([^"]+)"')
    RE_AREA = re.compile(r"地区：([^\s]+)")
    RE_YEAR = re.compile(r"年份：(\d+)")
    RE_KEY_URI = re.compile(r'URI="([^"]+)"')

    FALLBACK_LINES = [
        ("自营", "https://svip.qlplayer.cyou/?url="),
        ("闪电", "https://bfq.txnp.cn/excessive?url="),
        ("七哥", "https://jx.nnxv.cn/tv.php?url="),
        ("极速", "https://jx.2s0.cn/player/?url="),
        ("七七", "https://jx.77flv.cc/?url="),
        ("Super", "https://super.playr.top/?url="),
        ("盘古", "https://www.pangujiexi.com/jiexi/?url="),
        ("冰豆", "https://bd.jx.cn/?url="),
    ]

    # 容易在 Windows 端觸發 TLS/SSL 憑證握手失敗的 CDN 網域關鍵字
    SSL_BYPASS_DOMAINS = ("wsyzym3u8.com", "yzzy", "heimuertv.com")

    def getName(self):
        return "片库4K"

    def init(self, extend=""):
        self.host = "https://4k01.pianku.online"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": f"{self.host}/",
        }
        self.categories = [
            {"type_id": "20", "type_name": "电影"},
            {"type_id": "37", "type_name": "剧集"},
            {"type_id": "43", "type_name": "动漫"},
            {"type_id": "45", "type_name": "综艺"},
            {"type_id": "47", "type_name": "B站"},
            {"type_id": "21", "type_name": "动作片"},
            {"type_id": "22", "type_name": "喜剧片"},
            {"type_id": "23", "type_name": "爱情片"},
        ]
        try:
            import requests as _rq
            self._sess = _rq.Session()
            self._sess.headers.update(self.headers)
            self._sess.verify = False
        except Exception:
            self._sess = None

        self._search_ok = 0.0
        self._plines = []
        self._plines_ts = 0.0

    # ==================== 網路與 HTML 基礎工具 ====================

    def _req(self, method, url, data=None, timeout=15):
        try:
            if self._sess is not None:
                r = self._sess.request(method, url, data=data, timeout=timeout, verify=False)
            elif method == "GET":
                r = self.fetch(url, headers=self.headers, timeout=timeout, verify=False)
            else:
                r = self.post(url, data=data, headers=self.headers, timeout=timeout, verify=False)
            r.encoding = "utf-8"
            return r
        except Exception:
            return None

    def _get(self, url):
        r = self._req("GET", url)
        if r is not None and getattr(r, "status_code", 200) == 200:
            return r.text
        return None

    def _fix(self, url):
        if not url:
            return ""
        if url.startswith("//"):
            return f"https:{url}"
        if url.startswith("/"):
            return f"{self.host}{url}"
        return url

    @staticmethod
    def _html(content):
        if not content:
            return None
        try:
            return etree.HTML(content.encode("utf-8"))
        except Exception:
            return None

    # ==================== 解析與播放標頭輔助方法 ====================

    def _parse_lines(self):
        now = time.time()
        if self._plines and (now - self._plines_ts < 3600):
            return self._plines

        html = self._get(
            f"{self.host}/player/?url=https://v.qq.com/x/cover/mzc002008kq4b47/f4102rcpbqv.html"
        )
        if html:
            matches = self.RE_PLINE.findall(html)
            lines = [(name.strip(), prefix) for prefix, name in matches if name.strip() and prefix]
            if lines:
                self._plines = lines
                self._plines_ts = now
                return self._plines

        return self.FALLBACK_LINES

    def _extract_player_url(self, html):
        """直接從已取得的播放頁 HTML 中提取 player_aaaa.url，避免重複網路請求"""
        if not html:
            return ""
        m = self.RE_PLAYER_DATA.search(html)
        if not m:
            return ""
        try:
            data = json.loads(m.group(1))
            return (data.get("url") or "").replace("\\/", "/")
        except Exception:
            return ""

    def _build_play_headers(self, target_url):
        """根據目標播放網址動態產生完整瀏覽器請求標頭"""
        parsed = urlparse(target_url)
        origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else self.host
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
            ),
            "Referer": f"{origin}/",
            "Origin": origin,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        }

    def _get_proxy_base(self):
        """優先透過基底類別動態取得本地代理網址，失敗時退回預設 9978 埠"""
        try:
            if hasattr(self, "getProxyUrl"):
                base = self.getProxyUrl()
                if base:
                    return base
        except Exception:
            pass
        return "http://127.0.0.1:9978/proxy?do=py"

    def _build_proxy_url(self, media_type, target_url):
        base = self._get_proxy_base()
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}type={media_type}&url={quote(target_url, safe='')}"

    def _wrap_proxy_if_needed(self, video_url):
        """若目標 CDN 容易觸發 Windows 端 TLS/憑證錯誤，改走本地 localProxy 轉發"""
        netloc = urlparse(video_url).netloc.lower()
        if any(d in netloc for d in self.SSL_BYPASS_DOMAINS):
            media_type = "m3u8" if ".m3u8" in video_url.lower() else "ts"
            return self._build_proxy_url(media_type, video_url)
        return video_url

    def _cards(self, html):
        tree = self._html(html)
        if tree is None:
            return []

        out, seen = [], set()
        for a in tree.xpath('//div[contains(@class,"vod-item")]//a[contains(@href,"/voddetail/")]'):
            try:
                m = self.RE_VOD_ID.search(a.get("href", ""))
                if not m:
                    continue
                vid = m.group(1)
                if vid in seen:
                    continue
                seen.add(vid)

                name = (
                    a.get("title")
                    or "".join(a.xpath('.//h4[contains(@class,"title")]//text()'))
                ).strip()
                if not name:
                    continue

                img = a.xpath(".//img/@src")
                pic = self._fix(img[0] if img else "")
                rem = "".join(a.xpath('.//span[contains(@class,"remarks")]//text()')).strip()
                sub = "".join(a.xpath('.//p[contains(@class,"subtitle")]//text()')).strip()

                out.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": rem or sub,
                })
            except Exception:
                continue
        return out

    @staticmethod
    def _parse_pagecount(html, pattern, current_pg):
        if not html:
            return current_pg
        m = re.search(pattern, html)
        if m:
            return int(m.group(1))
        return current_pg + 1 if "下一页" in html else current_pg

    # ==================== 滑塊驗證碼計算（優化版） ====================

    def _png_x(self, data):
        idx = data.find(b"\x89PNG")
        if idx < 0:
            return None
        if idx > 0:
            data = data[idx:]

        pos, pal, idat, w, h = 8, None, bytearray(), 0, 0
        total_len = len(data)
        while pos + 8 <= total_len:
            ln = struct.unpack(">I", data[pos:pos + 4])[0]
            typ = data[pos + 4:pos + 8]
            chunk_end = pos + 8 + ln
            if chunk_end > total_len:
                break
            chunk = data[pos + 8:chunk_end]
            if typ == b"IHDR" and len(chunk) >= 8:
                w, h = struct.unpack(">II", chunk[:8])
            elif typ == b"PLTE":
                pal = chunk
            elif typ == b"IDAT":
                idat.extend(chunk)
            elif typ == b"IEND":
                break
            pos = chunk_end + 4

        if not pal or not idat or w != 240 or h != 450:
            return None

        try:
            raw = zlib.decompress(bytes(idat))
        except Exception:
            return None

        lum = [
            (pal[i] * 299 + pal[i + 1] * 587 + pal[i + 2] * 114) // 1000
            for i in range(0, len(pal), 3)
        ]

        rows = []
        prev = bytearray(w)
        p = 0
        for _ in range(h):
            f = raw[p]
            p += 1
            line = bytearray(raw[p:p + w])
            p += w
            if f == 1:
                for i in range(1, w):
                    line[i] = (line[i] + line[i - 1]) & 255
            elif f == 2:
                for i in range(w):
                    line[i] = (line[i] + prev[i]) & 255
            elif f == 3:
                line[0] = (line[0] + (prev[0] >> 1)) & 255
                for i in range(1, w):
                    line[i] = (line[i] + ((line[i - 1] + prev[i]) >> 1)) & 255
            elif f == 4:
                for i in range(w):
                    a = line[i - 1] if i > 0 else 0
                    b = prev[i]
                    c = prev[i - 1] if i > 0 else 0
                    pp = a + b - c
                    pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                    pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                    line[i] = (line[i] + pr) & 255
            elif f != 0:
                return None
            rows.append(line)
            prev = line

        th = h // 3
        offset = 2 * th
        col = [
            sum(abs(lum[rows[y][x]] - lum[rows[y + offset][x]]) for y in range(th))
            for x in range(w)
        ]

        win_w = 50
        curr_sum = sum(col[:win_w])
        best_sum = curr_sum
        best_x = 0
        for i in range(1, w - win_w + 1):
            curr_sum += col[i + win_w - 1] - col[i - 1]
            if curr_sum > best_sum:
                best_sum = curr_sum
                best_x = i
        return best_x

    def _search_pass(self):
        if time.time() < self._search_ok - 30:
            return True

        for _ in range(8):
            try:
                r = self._req("GET", f"{self.host}/SlideCaptcha.php?action=get&t={time.time()}")
                if r is None or b"\x89PNG" not in r.content[:60]:
                    continue
                x = self._png_x(r.content)
                if x is None:
                    continue
                c = self._req("GET", f"{self.host}/SlideCaptcha.php?action=check&x={x}&t={time.time():.6f}")
                if c is None or c.text.strip() != "ok":
                    continue
                v = self._req("POST", f"{self.host}/verify/search_complete.html", data={"source": "search"})
                d = json.loads(v.text) if v is not None else {}
                if str(d.get("code", "")) == "1":
                    self._search_ok = time.time() + int(d.get("expires", 300))
                    return True
            except Exception:
                continue
        return False

    # ==================== 爬蟲核心介面 ====================

    def homeContent(self, filter):
        return {
            "class": self.categories,
            "list": self._cards(self._get(f"{self.host}/")),
            "filters": {},
        }

    def homeVideoContent(self):
        return {"list": self._cards(self._get(f"{self.host}/"))}

    def categoryContent(self, tid, pg, filter, extend):
        pg = max(1, int(pg or 1))
        url = f"{self.host}/vodtype/{tid}.html" if pg == 1 else f"{self.host}/vodtype/{tid}-{pg}.html"
        html = self._get(url)
        items = self._cards(html)
        pc = self._parse_pagecount(
            html,
            rf'/vodtype/{re.escape(str(tid))}-(\d+)\.html"\s+title="尾页"',
            pg,
        )
        return {
            "page": pg,
            "pagecount": pc,
            "limit": len(items),
            "total": len(items) * pc,
            "list": items,
        }

    def _fetch_single_detail(self, vid):
        try:
            html = self._get(f"{self.host}/voddetail/{vid}.html")
            tree = self._html(html)
            if tree is None:
                return None

            name = (
                "".join(tree.xpath('//h1[contains(@class,"detail-title")]/text()')).strip()
                or "".join(tree.xpath('//h1[contains(@class,"detail-title")]//text()')).strip()
            )
            if not name:
                return None

            rem = "".join(
                tree.xpath('//h1[contains(@class,"detail-title")]//span[contains(@class,"detail-remarks")]//text()')
            ).strip()
            img = tree.xpath('//div[contains(@class,"detail-poster")]//img/@src')
            pic = self._fix(img[0] if img else "")

            meta = [
                "".join(tree.xpath(f'//div[contains(@class,"detail-meta")][{i}]//text()')).strip()
                for i in (1, 2, 3)
            ]
            area_m = self.RE_AREA.search(meta[0])
            year_m = self.RE_YEAR.search(meta[0])
            area = area_m.group(1) if area_m else ""
            year = year_m.group(1) if year_m else ""
            director = meta[1].replace("导演：", "").strip()
            actor = meta[2].replace("主演：", "").strip()
            desc = "".join(tree.xpath('//div[contains(@class,"detail-desc")]//p//text()')).strip()

            first_href = (
                tree.xpath('//a[contains(@class,"btn-play")]/@href')
                or tree.xpath('//a[contains(@href,"/vodplay/")]/@href')
                or [""]
            )[0]
            first_play_url = self._fix(first_href)

            play_html = self._get(first_play_url) if first_play_url else None
            play_tree = self._html(play_html)

            sources, episodes = [], []
            for t in ([play_tree] if play_tree is not None else []) + [tree]:
                tab_map = {}
                for s in t.xpath('//span[contains(@class,"source-tab-item")]'):
                    tab_name = "".join(s.xpath(".//text()")).strip()
                    target = (s.get("data-target") or "").strip()
                    if tab_name and target:
                        tab_map[target] = tab_name

                for pane in t.xpath('//div[contains(@class,"source-pane")]'):
                    eps = []
                    for a in pane.xpath('.//a[contains(@href,"/vodplay/")]'):
                        ep_name = (a.get("title") or "".join(a.xpath(".//text()"))).strip() or "正片"
                        eps.append(f"{ep_name}${self._fix(a.get('href', ''))}")
                    if eps:
                        grp = tab_map.get(pane.get("id", ""), f"线路{len(sources) + 1}")
                        joined = "#".join(eps)
                        if not episodes or episodes[-1] != joined or sources[-1] != grp:
                            sources.append(grp)
                            episodes.append(joined)
                if sources:
                    break

            if not sources and first_play_url:
                sources, episodes = ["正片"], [f"正片${first_play_url}"]
            if not sources:
                return None

            plines = self._parse_lines()
            canon = max(episodes, key=lambda e: e.count("#"))
            eps_list = canon.split("#")
            first_ep_url = eps_list[0].split("$", 1)[1] if "$" in eps_list[0] else first_play_url

            target_html = play_html if first_ep_url == first_play_url else self._get(first_ep_url)
            outer = self._extract_player_url(target_html)

            if plines and outer.startswith("http") and not self.RE_VIDEO_EXT.search(outer):
                play_from = "$$$".join(n for n, _ in plines)
                play_url = "$$$".join(canon for _ in plines)
            else:
                play_from = "$$$".join(sources)
                play_url = "$$$".join(episodes)

            return {
                "vod_id": vid,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": rem,
                "vod_area": area,
                "vod_year": year,
                "vod_director": director,
                "vod_actor": actor,
                "vod_content": desc,
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }
        except Exception:
            return None

    def detailContent(self, ids):
        if not ids:
            return {"list": []}
        if len(ids) == 1:
            item = self._fetch_single_detail(ids[0])
            return {"list": [item] if item else []}

        with ThreadPoolExecutor(max_workers=min(4, len(ids))) as pool:
            items = [res for res in pool.map(self._fetch_single_detail, ids) if res]
        return {"list": items}

    def searchContent(self, key, quick, pg="1"):
        pg = max(1, int(pg or 1))
        if not self._search_pass():
            return {"list": [], "page": pg, "pagecount": pg, "limit": 0, "total": 0}

        encoded_key = quote(key)
        url = (
            f"{self.host}/vodsearch/{encoded_key}-------------.html"
            if pg == 1
            else f"{self.host}/vodsearch/{encoded_key}----------{pg}---.html"
        )
        html = self._get(url)
        items = self._cards(html)
        pc = self._parse_pagecount(
            html,
            rf'/vodsearch/{re.escape(encoded_key)}----------(\d+)---\.html"\s+title="尾页"',
            pg,
        )
        return {
            "list": items,
            "page": pg,
            "pagecount": pc,
            "limit": len(items),
            "total": len(items) * pc,
        }

    def playerContent(self, flag, id, vipFlags):
        url = self._fix(id)
        lines_list = self._parse_lines()
        plines = dict(lines_list)

        known_line_hosts = {urlparse(prefix).netloc for _, prefix in lines_list if prefix}
        parsed_url = urlparse(url)
        host_domain = urlparse(self.host).netloc

        if flag in plines and url.startswith("http") and f"{host_domain}/vodplay/" in url:
            outer = self._extract_player_url(self._get(url))
            if outer.startswith("http") and not self.RE_VIDEO_EXT.search(outer):
                raw = unquote(url)
                if "/player/?url=" in raw:
                    outer = unquote(raw.split("/player/?url=", 1)[1].split("&")[0])
                return {
                    "parse": 1,
                    "jx": 1,
                    "url": plines[flag] + quote(outer, safe=""),
                    "header": json.dumps(self._build_play_headers(outer)),
                }

        if "/player/?url=" in url or (parsed_url.netloc and parsed_url.netloc in known_line_hosts):
            return {
                "parse": 1,
                "jx": 1,
                "url": url,
                "header": json.dumps(self._build_play_headers(url)),
            }

        html = self._get(url)
        if html:
            u = self._extract_player_url(html)
            if u.startswith("http"):
                is_direct = bool(self.RE_VIDEO_EXT.search(u))
                final_url = self._wrap_proxy_if_needed(u) if is_direct else u
                return {
                    "parse": 0 if is_direct else 1,
                    "url": final_url,
                    "header": json.dumps(self._build_play_headers(u)),
                }

            m = self.RE_M3U8_URL.search(html)
            if m:
                u = m.group(1)
                return {
                    "parse": 0,
                    "url": self._wrap_proxy_if_needed(u),
                    "header": json.dumps(self._build_play_headers(u)),
                }

        return {
            "parse": 1,
            "url": url,
            "header": json.dumps(self._build_play_headers(url)),
        }

    def isVideoFormat(self, url):
        return bool(self.RE_VIDEO_EXT.search(url or ""))

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        """接管 m3u8 請求並忽略 SSL 憑證驗證，同時將內部的切片與金鑰重寫為本地代理路徑"""
        target_url = unquote(param.get("url", ""))
        if not target_url.startswith("http"):
            return None

        req_type = param.get("type", "m3u8")
        headers = self._build_play_headers(target_url)

        try:
            if self._sess is not None:
                resp = self._sess.get(target_url, headers=headers, timeout=15, verify=False)
            else:
                resp = self.fetch(target_url, headers=headers, timeout=15, verify=False)

            if req_type == "m3u8":
                base_url = target_url.rsplit("/", 1)[0] + "/"
                parsed_target = urlparse(target_url)
                root_url = f"{parsed_target.scheme}://{parsed_target.netloc}"
                lines = []

                for line in resp.text.splitlines():
                    s = line.strip()
                    if not s:
                        lines.append(line)
                        continue

                    if s.startswith("#EXT-X-KEY") and 'URI="' in s:
                        def _repl_key(m):
                            k_url = m.group(1)
                            if not k_url.startswith("http"):
                                k_url = (root_url + k_url) if k_url.startswith("/") else (base_url + k_url)
                            return f'URI="{self._build_proxy_url("ts", k_url)}"'

                        line = self.RE_KEY_URI.sub(_repl_key, line)
                    elif not s.startswith("#"):
                        if s.startswith("http"):
                            seg_url = s
                        elif s.startswith("/"):
                            seg_url = root_url + s
                        else:
                            seg_url = base_url + s

                        # 若為多碼率主清單（子項仍為 .m3u8），遞迴維持 type=m3u8
                        sub_type = "m3u8" if ".m3u8" in seg_url.lower() else "ts"
                        line = self._build_proxy_url(sub_type, seg_url)

                    lines.append(line)

                content = "\n".join(lines).encode("utf-8")
                return [200, "application/vnd.apple.mpegurl", content]

            content_type = resp.headers.get("Content-Type", "video/mp2t")
            return [200, content_type, resp.content]
        except Exception:
            return None

    def destroy(self):
        if self._sess is not None:
            try:
                self._sess.close()
            except Exception:
                pass
        return None

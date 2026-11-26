# coding=utf-8
#!/usr/bin/python
import base64
import json
import re
import sys
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from lxml import etree
import requests
import urllib3

# 關閉忽略 SSL 憑證時的警告訊息
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def __init__(self):
        self.host = "https://www.qivod.com"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,zh-TW;q=0.8,en;q=0.7",
            "Referer": f"{self.host}/",
        }

    def getName(self):
        return "奇优影院"

    def init(self, extend=""):
        if extend and extend.startswith("http"):
            self.host = extend.rstrip("/")
            self.headers["Referer"] = f"{self.host}/"

    def homeContent(self, filter):
        cateManual = {
            "电影": "1",
            "电视剧": "2",
            "动漫": "3",
            "综艺": "4",
        }
        classes = [{'type_name': k, 'type_id': v} for k, v in cateManual.items()]
        sort_filter = [{
            "key": "by",
            "name": "排序",
            "value": [
                {"n": "按时间", "v": "time"},
                {"n": "按人气", "v": "hit"},
            ],
        }]
        filters = {cid: sort_filter for cid in ["1", "2", "3", "4"]}
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        try:
            rsp = self.fetch(f"{self.host}/", headers=self.headers)
            root = self.parse_html(rsp.content)
            if root is None:
                return {'list': []}
            return {'list': self.extract_cards_with_fallback(root)}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        order = extend.get('by', 'time') if extend else 'time'
        candidate_urls = [
            f"{self.host}/vod-type-id-{tid}-pg-{pg}.html",
            f"{self.host}/list/{tid}_{pg}.html?order={order}",
            f"{self.host}/type/{tid}-{pg}.html",
        ]
        if order == "hit":
            candidate_urls.insert(0, f"{self.host}/vod-type-id-{tid}-pg-{pg}-order-hit.html")

        for url in candidate_urls:
            try:
                rsp = self.fetch(url, headers=self.headers)
                if getattr(rsp, "status_code", 0) >= 400:
                    continue
                root = self.parse_html(rsp.content)
                if root is None:
                    continue

                videos = self.extract_cards_with_fallback(root)
                if videos:
                    page_numbers = []
                    for link in root.xpath("//ul[contains(@class,'stui-page')]//a/@href"):
                        m = re.search(r'(?:pg-|_)(\d+)\.html', link)
                        if m:
                            page_numbers.append(int(m.group(1)))
                    total_page = max(page_numbers) if page_numbers else 999

                    return {
                        'list': videos,
                        'page': int(pg),
                        'pagecount': total_page,
                        'limit': len(videos),
                        'total': total_page * len(videos),
                    }
            except Exception:
                continue

        return {'list': [], 'page': int(pg), 'pagecount': 1, 'limit': 90, 'total': 0}

    def detailContent(self, array):
        try:
            tid = array[0]
            url = urljoin(self.host, tid)
            rsp = self.fetch(url, headers=self.headers)
            root = self.parse_html(rsp.content)
            if root is None:
                return {'list': []}

            detail_node = (
                root.xpath("//div[contains(@class,'stui-content__detail')]")
                or root.xpath("//div[@class='stui-player__detail']")
            )
            pic = title = area = director = actor = year = desc = ""

            if detail_node:
                node = detail_node[0]
                pic = self.get_first(
                    root.xpath("//meta[@property='og:image']/@content")
                    or node.xpath(".//img/@data-original")
                    or node.xpath(".//img/@src")
                )
                if pic:
                    pic = urljoin(self.host, pic)

                title = self.get_first(node.xpath(".//h1//text()")).strip()
                if not title:
                    page_title = self.get_first(root.xpath("//title/text()"))
                    m = re.search(r"《(.*?)》", page_title)
                    title = m.group(1) if m else ""

                area = self.get_first(root.xpath("//meta[@property='og:video:area']/@content"))
                director = self.get_first(root.xpath("//meta[@property='og:video:director']/@content"))
                actor = self.get_first(root.xpath("//meta[@property='og:video:actor']/@content"))
                year_info = self.get_first(root.xpath("//p[@class='data']//text()[contains(.,'年份：')]"))
                ym = re.search(r"年份：(\d{4})", year_info)
                year = ym.group(1) if ym else ""
                desc = self.get_first(root.xpath("//meta[@property='og:description']/@content"))

            playFrom, playUrl = [], []
            for tab in root.xpath("//ul[contains(@class,'nav-tabs')]/li"):
                tab_name = self.get_first(tab.xpath(".//a/text()")).strip()
                tab_id = self.get_first(tab.xpath(".//a/@href")).replace("#", "").strip()

                if tab_name and tab_id:
                    play_list = root.xpath(
                        f"//div[@id='{tab_id}']//ul[contains(@class,'stui-content__playlist')]//a"
                    )
                    if play_list:
                        episodes = []
                        for ep in play_list:
                            ep_name = self.get_first(ep.xpath("./text()")).strip() or "播放"
                            ep_url = self.get_first(ep.xpath("./@href")).strip()
                            if ep_url:
                                episodes.append(f"{ep_name}${ep_url}")
                        if episodes:
                            playFrom.append(tab_name)
                            playUrl.append("#".join(episodes))

            if not playFrom:
                playlists = root.xpath("//ul[contains(@class,'stui-content__playlist')]")
                for idx, pl in enumerate(playlists, start=1):
                    episodes = []
                    for ep in pl.xpath(".//a"):
                        ep_name = self.get_first(ep.xpath("./text()")).strip() or "播放"
                        ep_url = self.get_first(ep.xpath("./@href")).strip()
                        if ep_url:
                            episodes.append(f"{ep_name}${ep_url}")
                    if episodes:
                        playFrom.append(f"线路{idx}")
                        playUrl.append("#".join(episodes))

            vod = {
                "vod_id": tid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_year": year,
                "vod_area": area,
                "vod_actor": actor,
                "vod_director": director,
                "vod_content": desc,
            }

            if playFrom and playUrl:
                vod['vod_play_from'] = "$$$".join(playFrom)
                vod['vod_play_url'] = "$$$".join(playUrl)

            return {'list': [vod]}
        except Exception:
            return {'list': []}

    def searchContent(self, key, quick, page='1'):
        try:
            url = f"{self.host}/search.php"
            post_data = {'searchword': key}
            headers = {
                **self.headers,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Origin": self.host,
            }
            rsp = self.post(url, data=post_data, headers=headers)
            root = self.parse_html(rsp.content)
            videos = self.extract_cards_with_fallback(root) if root is not None else []

            if not videos:
                get_url = f"{self.host}/vod-search-pg-{page}-wd-{quote(key)}.html"
                rsp_get = self.fetch(get_url, headers=self.headers)
                root_get = self.parse_html(rsp_get.content)
                if root_get is not None:
                    videos = self.extract_cards_with_fallback(root_get)

            return {'list': videos}
        except Exception:
            return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        play_page_url = urljoin(self.host, id)
        page_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": play_page_url,
        }
        media_headers = {
            "User-Agent": self.headers["User-Agent"],
        }

        try:
            rsp = self.fetch(play_page_url, headers=page_headers)
            _, raw_html = self.parse_html(rsp.content, return_content=True)

            # 收集頁面上與所有外部 JS / iframe 中的全部候選串流網址
            candidates = []
            self._collect_streams_in_text(raw_html, candidates)

            ignore_js = ("jquery", "bootstrap", "stui", "swiper", "layer", "lazyload", "tj", "tongji")
            script_srcs = re.findall(r'<script[^>]*src=[\'"]([^\'"]+\.js[^\'"]*)[\'"]', raw_html, re.IGNORECASE)
            for src in script_srcs:
                if any(k in src.lower() for k in ignore_js):
                    continue
                try:
                    js_rsp = self.fetch(urljoin(play_page_url, src), headers=page_headers)
                    self._collect_streams_in_text(js_rsp.content.decode('utf-8', errors='replace'), candidates)
                except Exception:
                    continue

            for iframe_src in re.findall(r'<iframe[^>]*src=[\'"]([^\'"]+)[\'"]', raw_html, re.IGNORECASE):
                self._collect_streams_in_text(iframe_src, candidates)
                try:
                    iframe_rsp = self.fetch(urljoin(play_page_url, iframe_src), headers=page_headers)
                    self._collect_streams_in_text(iframe_rsp.text, candidates)
                except Exception:
                    continue

            # 逐一驗證候選串流：優先挑選 Python 本地代理能直接拿到 #EXTM3U 的有效網址
            for stream_url in candidates:
                if ".m3u8" in stream_url:
                    if self._check_m3u8_reachable(stream_url, play_page_url):
                        proxy_url = (
                            f"{self.getProxyUrl()}&url={quote(stream_url, safe='')}"
                            f"&ref={quote(play_page_url, safe='')}"
                        )
                        return {"parse": 0, "playUrl": "", "url": proxy_url, "header": media_headers}

            # 若 Python 端探測全數被 CDN 擋下（例如 TLS 指紋限制），直接把第一個抓到的真實網址交給播放器核心直連
            if candidates:
                return {"parse": 0, "playUrl": "", "url": candidates[0], "header": media_headers}

            return {"parse": 1, "playUrl": "", "url": play_page_url, "header": page_headers}

        except Exception:
            return {"parse": 1, "playUrl": "", "url": play_page_url, "header": page_headers}

    def localProxy(self, param):
        """本地代理：支援自動繞過系統代理、多 Referer 策略與真實錯誤透傳"""
        target_url = unquote(param.get("url", ""))
        ref_url = unquote(param.get("ref", ""))
        if not target_url:
            return [404, "text/plain", b"Missing url"]

        parsed_target = urlparse(target_url)
        target_origin = f"{parsed_target.scheme}://{parsed_target.netloc}/"

        header_candidates = [
            {"User-Agent": self.headers["User-Agent"]},
            {"User-Agent": self.headers["User-Agent"], "Referer": target_origin, "Origin": target_origin.rstrip("/")},
        ]
        if ref_url:
            header_candidates.append({"User-Agent": self.headers["User-Agent"], "Referer": ref_url})

        proxy_modes = [None, {"http": None, "https": None}]

        rsp = None
        last_status = "無回應"
        last_snippet = ""

        for p_mode in proxy_modes:
            for h in header_candidates:
                try:
                    r = requests.get(
                        target_url,
                        headers=h,
                        proxies=p_mode,
                        verify=False,
                        timeout=10,
                        allow_redirects=True,
                    )
                    last_status = f"HTTP {r.status_code}"
                    last_snippet = r.text[:120].replace("\n", " ")

                    if r.status_code == 200 and len(r.content) > 0:
                        if ".m3u8" in target_url:
                            if "#EXTM3U" in r.text:
                                rsp = r
                                break
                        else:
                            rsp = r
                            break
                except Exception as e:
                    last_status = f"連線異常: {type(e).__name__}"
                    last_snippet = str(e)[:100]
                    continue
            if rsp is not None:
                break

        if rsp is None:
            err_msg = f"[{last_status}] URL: {target_url} | Body: {last_snippet}"
            return [502, "text/plain", err_msg.encode("utf-8")]

        final_base_url = rsp.url
        content_type = rsp.headers.get("Content-Type", "application/vnd.apple.mpegurl")

        if ".m3u8" in target_url or "mpegurl" in content_type.lower() or rsp.text.lstrip().startswith("#EXTM3U"):
            lines = []
            for line in rsp.text.splitlines():
                stripped = line.strip()
                if not stripped:
                    lines.append(line)
                elif stripped.startswith("#"):
                    if 'URI="' in stripped:
                        def _replace_uri(m):
                            full_key_url = urljoin(final_base_url, m.group(1))
                            proxied_key = (
                                f"{self.getProxyUrl()}&url={quote(full_key_url, safe='')}"
                                f"&ref={quote(ref_url, safe='')}"
                            )
                            return f'URI="{proxied_key}"'
                        stripped = re.sub(r'URI="([^"]+)"', _replace_uri, stripped)
                    lines.append(stripped)
                else:
                    abs_url = urljoin(final_base_url, stripped)
                    lines.append(
                        f"{self.getProxyUrl()}&url={quote(abs_url, safe='')}"
                        f"&ref={quote(ref_url, safe='')}"
                    )

            body = "\n".join(lines).encode("utf-8")
            return [200, "application/vnd.apple.mpegurl", body]

        return [rsp.status_code, content_type, rsp.content]

    def _check_m3u8_reachable(self, target_url, ref_url):
        """快速檢查目標 m3u8 是否能正常回傳 #EXTM3U"""
        parsed = urlparse(target_url)
        origin = f"{parsed.scheme}://{parsed.netloc}/"
        headers_list = [
            {"User-Agent": self.headers["User-Agent"]},
            {"User-Agent": self.headers["User-Agent"], "Referer": origin},
            {"User-Agent": self.headers["User-Agent"], "Referer": ref_url},
        ]
        for p_mode in [None, {"http": None, "https": None}]:
            for h in headers_list:
                try:
                    r = requests.get(target_url, headers=h, proxies=p_mode, verify=False, timeout=6)
                    if r.status_code == 200 and "#EXTM3U" in r.text:
                        return True
                except Exception:
                    continue
        return False

    def _collect_streams_in_text(self, text, candidates):
        """將文本中所有解碼後的 m3u8 / mp4 網址依序加入 candidates 列表（去重）"""
        if not text:
            return

        for unesc_match in re.findall(r'unescape\([\'"]([^\'"]+)[\'"]\)', text):
            self._collect_streams_in_text(unquote(unesc_match), candidates)

        for b64_match in re.findall(r'atob\([\'"]([A-Za-z0-9+/=]+)[\'"]\)', text):
            try:
                decoded = base64.b64decode(b64_match).decode('utf-8', errors='ignore')
                self._collect_streams_in_text(decoded, candidates)
            except Exception:
                pass

        cleaned = unquote(text.replace(r"\/", "/"))

        for ali_match in re.finditer(r'/player/aliplayer\.html\?[^"\'\s<>]+', cleaned):
            qs = parse_qs(urlparse(ali_match.group(0)).query)
            if "url" in qs and qs["url"][0]:
                u = unquote(qs["url"][0]).strip()
                if u not in candidates:
                    candidates.append(u)

        for m in re.finditer(r'https?://[^\s"\'<>\\$#]+\.(?:m3u8|mp4)(?:\?[^\s"\'<>\\$#]*)?', cleaned, re.IGNORECASE):
            u = m.group(0).strip()
            if "aliplayer.html" not in u and u not in candidates:
                candidates.append(u)

    # ================= 片卡解析與輔助工具 =================

    def extract_cards_with_fallback(self, root):
        xpath_rules = [
            "//a[contains(@class,'stui-vodlist__thumb')]",
            "//a[contains(@class,'vodlist__thumb')]",
            "//a[contains(@href,'vod-detail-id-')]",
            "//a[contains(@href,'/vod/') and (@title or .//img or @style)]",
        ]
        for rule in xpath_rules:
            nodes = root.xpath(rule)
            if nodes:
                videos = self.parse_vod_list(nodes)
                if videos:
                    return videos
        return []

    def parse_vod_list(self, a_nodes):
        videos = []
        seen = set()

        for a in a_nodes:
            try:
                href = self.get_first(a.xpath("./@href")).strip()
                if not href or href in seen or href.startswith("javascript"):
                    continue

                title = (
                    self.get_first(a.xpath("./@title")).strip()
                    or self.get_first(a.xpath(".//span[contains(@class,'pic-text')]/text()")).strip()
                    or self.get_first(a.xpath(".//img/@alt")).strip()
                    or self.get_first(a.xpath(".//text()")).strip()
                )
                if not title:
                    continue

                pic = ""
                style = self.get_first(a.xpath("./@style"))
                if style:
                    bg_match = re.search(r"background(?:-image)?\s*:\s*url\(['\"]?(.*?)['\"]?\)", style)
                    if bg_match:
                        pic = bg_match.group(1).strip()

                if not pic:
                    pic = (
                        self.get_first(a.xpath("./@data-original")).strip()
                        or self.get_first(a.xpath(".//img/@data-original")).strip()
                        or self.get_first(a.xpath(".//img/@src")).strip()
                    )

                if pic:
                    pic = urljoin(self.host, pic)

                remark = self.get_first(
                    a.xpath(".//span[contains(@class,'pic-text')]/text()")
                ).strip()
                if remark == title:
                    remark = ""

                seen.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark,
                })
            except Exception:
                continue

        return videos

    def parse_html(self, content, return_content=False):
        if isinstance(content, str):
            html_content = content
        else:
            html_content = None
            for encoding in ['utf-8', 'gbk', 'gb2312', 'iso-8859-1']:
                try:
                    html_content = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if html_content is None:
                html_content = content.decode('utf-8', errors='replace')

        html_content = self.clean_html(html_content)
        root = etree.HTML(html_content)
        return (root, html_content) if return_content else root

    def get_first(self, array, default=""):
        return array[0] if array else default

    def clean_html(self, html_content):
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', html_content)

    def isVideoFormat(self, url):
        return any(fmt in url for fmt in ['.m3u8', '.mp4', '.avi', '.mkv', '.flv', '.webm'])

    def manualVideoCheck(self):
        return True

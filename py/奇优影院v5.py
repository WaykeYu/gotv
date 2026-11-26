# coding=utf-8
#!/usr/bin/python
import json
import re
import sys
from urllib.parse import parse_qs, quote, unquote, urljoin, urlparse
from lxml import etree

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
        req_headers = {
            "User-Agent": self.headers["User-Agent"],
            "Referer": play_page_url,
        }

        try:
            rsp = self.fetch(play_page_url, headers=req_headers)
            _, raw_html = self.parse_html(rsp.content, return_content=True)

            # 將 JS 常見的轉義斜線 \/ 還原為 /，方便統一正則匹配
            html_content = raw_html.replace(r"\/", "/")

            # 1. 優先提取 /player/aliplayer.html?url=... 裡的真實影片串流
            ali_match = re.search(r'/player/aliplayer\.html\?[^"\'\s<>]+', html_content)
            if ali_match:
                qs = parse_qs(urlparse(ali_match.group(0)).query)
                if "url" in qs and qs["url"][0]:
                    real_url = unquote(qs["url"][0])
                    return {"parse": 0, "playUrl": "", "url": real_url, "header": req_headers}

            # 2. 提取 JS 變數中的播放位址 (海洋CMS 常見: var now="...", var url="...", player_data={...})
            js_patterns = [
                r'var\s+(?:now|url|playurl|video_url)\s*=\s*[\'"]([^\'"]+\.(?:m3u8|mp4)[^\'"]*)[\'"]',
                r'"url"\s*:\s*[\'"](https?://[^\'"]+\.(?:m3u8|mp4)[^\'"]*)[\'"]',
                r'aliplayer\.html\?url=[\'"]?\s*\+\s*[\'"]([^\'"]+)[\'"]',
            ]
            for pat in js_patterns:
                m = re.search(pat, html_content, re.IGNORECASE)
                if m:
                    real_url = unquote(m.group(1))
                    return {"parse": 0, "playUrl": "", "url": real_url, "header": req_headers}

            # 3. 追蹤頁面中的 iframe 播放器或外部 player JS 檔案
            for iframe_src in re.findall(r'<iframe[^>]*src=[\'"]([^\'"]+)[\'"]', html_content):
                if "url=" in iframe_src:
                    qs = parse_qs(urlparse(iframe_src).query)
                    if "url" in qs and qs["url"][0]:
                        return {"parse": 0, "playUrl": "", "url": unquote(qs["url"][0]), "header": req_headers}

                full_iframe = urljoin(play_page_url, iframe_src)
                try:
                    iframe_rsp = self.fetch(full_iframe, headers=req_headers)
                    iframe_text = iframe_rsp.text.replace(r"\/", "/")
                    m3u8_match = re.search(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*', iframe_text)
                    if m3u8_match:
                        return {"parse": 0, "playUrl": "", "url": unquote(m3u8_match.group(0)), "header": req_headers}
                except Exception:
                    continue

            # 4. 追蹤海洋CMS 動態生成的播放資料 JS (常見為 /upload/playdata/...js)
            for js_src in re.findall(r'<script[^>]*src=[\'"]([^\'"]*playdata[^\'"]*\.js[^\'"]*)[\'"]', html_content):
                full_js = urljoin(play_page_url, js_src)
                try:
                    js_rsp = self.fetch(full_js, headers=req_headers)
                    js_text = unquote(js_rsp.text.replace(r"\/", "/"))
                    m3u8_match = re.search(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*', js_text)
                    if m3u8_match:
                        return {"parse": 0, "playUrl": "", "url": m3u8_match.group(0), "header": req_headers}
                except Exception:
                    continue

            # 5. 全文直接搜尋任何 m3u8 或 mp4 串流網址
            m3u8_match = re.search(r'https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*', html_content)
            if m3u8_match:
                return {"parse": 0, "playUrl": "", "url": unquote(m3u8_match.group(0)), "header": req_headers}

            # 6. 若全部未命中，回傳 parse: 0 並帶入原始頁面嘗試播放器內建嗅探（避免無解析接口直接報錯）
            return {"parse": 0, "playUrl": "", "url": play_page_url, "header": req_headers}

        except Exception:
            return {"parse": 0, "playUrl": "", "url": play_page_url, "header": req_headers}

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

    def localProxy(self, param):
        return {}

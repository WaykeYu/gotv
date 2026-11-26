# coding=utf-8
#!/usr/bin/python
import re
import sys
from urllib.parse import parse_qs, urljoin, urlparse
from lxml import etree

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):

    def __init__(self):
        # 預設改用 https，並可透過 json 設定檔的 ext 欄位動態傳入最新網域
        self.host = "https://www.qiyoudy5.com"
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
        filters = {cid: sort_filter for cid in ["1", "2", "3", "4", "6"]}
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        try:
            rsp = self.fetch(f"{self.host}/", headers=self.headers)
            root, html_text = self.parse_html(rsp.content, return_content=True)
            if root is None:
                return {'list': [self._debug_card("HTML解析失敗", "root is None")]}

            videos = self.extract_cards_with_fallback(root)

            # 若抓不到片卡，回傳一筆診斷資訊卡片方便排查原因
            if not videos:
                page_title = self.get_first(root.xpath("//title/text()")).strip() or "無標題"
                status = getattr(rsp, "status_code", "未知狀態碼")
                return {
                    'list': [
                        self._debug_card(
                            f"未抓到片卡 (HTTP {status})",
                            f"網頁標題: {page_title} | 長度: {len(html_text)}",
                        )
                    ]
                }

            return {'list': videos}
        except Exception as e:
            return {'list': [self._debug_card("請求異常", str(e))]}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            order = extend.get('by', 'time') if extend else 'time'
            url = f"{self.host}/list/{tid}_{pg}.html?order={order}"
            rsp = self.fetch(url, headers=self.headers)
            root = self.parse_html(rsp.content)

            if root is None:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 90, 'total': 0}

            videos = self.extract_cards_with_fallback(root)

            active_pg = self.get_first(
                root.xpath("//ul[contains(@class,'stui-page')]//a[@class='active']/text()")
            )
            current_page = int(active_pg) if active_pg.isdigit() else int(pg)

            page_numbers = []
            for link in root.xpath("//ul[contains(@class,'stui-page')]//a[contains(@href,'list')]/@href"):
                match = re.search(r'list/\d+_(\d+)\.html', link)
                if match:
                    page_numbers.append(int(match.group(1)))
            total_page = max(page_numbers) if page_numbers else 999

            return {
                'list': videos,
                'page': current_page,
                'pagecount': total_page,
                'limit': 90,
                'total': 999999,
            }
        except Exception:
            return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 90, 'total': 0}

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

            # 若沒有 nav-tabs 分頁結構，直接抓取頁面上所有 playlist 區塊
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
            if root is None:
                return {'list': []}

            videos = self.extract_cards_with_fallback(root)
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
            _, html_content = self.parse_html(rsp.content, return_content=True)

            # 1. 精準解析 /player/aliplayer.html?url=https://...m3u8
            ali_match = re.search(
                r'/player/aliplayer\.html\?[^"\'\s<>]+', html_content
            )
            if ali_match:
                parsed = urlparse(ali_match.group(0))
                qs = parse_qs(parsed.query)
                if "url" in qs and qs["url"][0]:
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": qs["url"][0],
                        "header": req_headers,
                    }

            # 2. 追蹤 iframe 播放器
            for iframe_src in re.findall(r'<iframe[^>]*src=[\'"]([^\'"]+)[\'"]', html_content):
                if "url=" in iframe_src and ".m3u8" in iframe_src:
                    qs = parse_qs(urlparse(iframe_src).query)
                    if "url" in qs:
                        return {"parse": 0, "playUrl": "", "url": qs["url"][0], "header": req_headers}

                full_iframe = urljoin(play_page_url, iframe_src)
                try:
                    iframe_rsp = self.fetch(full_iframe, headers=req_headers)
                    m3u8_match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', iframe_rsp.text)
                    if m3u8_match:
                        return {"parse": 0, "playUrl": "", "url": m3u8_match.group(0), "header": req_headers}
                except Exception:
                    continue

            # 3. 頁面內直接暴露的 m3u8
            m3u8_match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html_content)
            if m3u8_match:
                return {"parse": 0, "playUrl": "", "url": m3u8_match.group(0), "header": req_headers}

            return {"parse": 1, "playUrl": "", "url": play_page_url, "header": req_headers}

        except Exception:
            return {"parse": 1, "playUrl": "", "url": play_page_url, "header": req_headers}

    # ================= 多層級片卡解析與診斷工具 =================

    def extract_cards_with_fallback(self, root):
        """依序嘗試多種 XPath 規則，確保抓得到片卡"""
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

    def _debug_card(self, title, remark):
        """在介面顯示診斷訊息，方便直接判讀失敗原因"""
        return {
            "vod_id": "debug",
            "vod_name": title,
            "vod_pic": "",
            "vod_remarks": remark,
        }

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

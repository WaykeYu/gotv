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
        # 集中管理最新網域，日後若網域變更只需修改此處
        self.host = "http://qiyoudy5.com"
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
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
            root = self.parse_html(rsp.content)
            if root is None:
                return {'list': []}

            # 統一提取首頁所有 stui-vodlist__thumb 片卡（包含輪播與推薦列表）
            videos = self.parse_vod_list(
                root.xpath("//a[contains(@class,'stui-vodlist__thumb')]")
            )
            return {'list': videos}
        except Exception:
            return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        try:
            order = extend.get('by', 'time') if extend else 'time'
            url = f"{self.host}/list/{tid}_{pg}.html?order={order}"
            rsp = self.fetch(url, headers=self.headers)
            root = self.parse_html(rsp.content)

            if root is None:
                return {'list': [], 'page': pg, 'pagecount': 1, 'limit': 90, 'total': 0}

            videos = self.parse_vod_list(
                root.xpath("//a[contains(@class,'stui-vodlist__thumb')]")
            )

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

            # 解析分頁路線與集數
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

            # 優先直接抓取所有片卡 a 標籤，相容列表與媒體卡片模式
            thumb_nodes = root.xpath("//a[contains(@class,'stui-vodlist__thumb')]")
            videos = self.parse_vod_list(thumb_nodes)

            # 備援：若搜尋頁改為純文字/詳情連結模式
            if not videos:
                fallback_nodes = root.xpath("//a[contains(@href,'vod-detail') or contains(@href,'/vod/')]")
                videos = self.parse_vod_list(fallback_nodes)

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

            # 1. 【最高優先】精準解析 /player/aliplayer.html?url=https://...m3u8
            ali_match = re.search(
                r'/player/aliplayer\.html\?[^"\'\s<>]+', html_content
            )
            if ali_match:
                parsed = urlparse(ali_match.group(0))
                qs = parse_qs(parsed.query)
                if "url" in qs and qs["url"][0]:
                    real_m3u8 = qs["url"][0]
                    return {
                        "parse": 0,
                        "playUrl": "",
                        "url": real_m3u8,
                        "header": req_headers,
                    }

            # 2. 備援：原站 API 介面
            for pattern in [
                r"http://api\.yongfan99\.com:81/content\.php\?[^'\"]+",
                r"content\.php\?vid=[^&]+&type=[^'\"]+",
            ]:
                match = re.search(pattern, html_content)
                if match:
                    api_url = match.group(0)
                    if not api_url.startswith('http'):
                        api_url = "http://api.yongfan99.com:81/" + api_url
                    try:
                        api_rsp = self.fetch(api_url, headers=req_headers)
                        m3u8_match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', api_rsp.text)
                        if m3u8_match:
                            return {"parse": 0, "playUrl": "", "url": m3u8_match.group(0), "header": req_headers}
                    except Exception:
                        pass

            # 3. 備援：追蹤其他 iframe 播放器
            for iframe_src in re.findall(r'<iframe[^>]*src=[\'"]([^\'"]+)[\'"]', html_content):
                # 若 iframe src 本身就夾帶 url=.m3u8 參數，直接拆解不需二次請求
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

            # 4. 備援：頁面內直接暴露的 m3u8
            m3u8_match = re.search(r'https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*', html_content)
            if m3u8_match:
                return {"parse": 0, "playUrl": "", "url": m3u8_match.group(0), "header": req_headers}

            # 5. 最終退回嗅探模式
            return {"parse": 1, "playUrl": "", "url": play_page_url, "header": req_headers}

        except Exception:
            return {"parse": 1, "playUrl": "", "url": play_page_url, "header": req_headers}

    # ================= 統一解析與輔助方法 =================

    def parse_vod_list(self, a_nodes):
        """統一解析片卡列表（相容 style="background: url(...)" 與 data-original）"""
        videos = []
        seen = set()

        for a in a_nodes:
            try:
                href = self.get_first(a.xpath("./@href")).strip()
                if not href or href in seen:
                    continue

                # 片名提取：優先 @title -> 內部 .pic-text -> 純文字
                title = (
                    self.get_first(a.xpath("./@title")).strip()
                    or self.get_first(a.xpath(".//span[contains(@class,'pic-text')]/text()")).strip()
                    or self.get_first(a.xpath(".//text()")).strip()
                )
                if not title:
                    continue

                # 封面圖提取：優先從 style="background: url(...)" 抓取，備援 data-original / src
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

                # 狀態角標提取（如：更新至XX集 / HD中字 / 片名副標）
                remark = self.get_first(
                    a.xpath(".//span[contains(@class,'pic-text')]/text()")
                ).strip()
                # 若角標文字跟片名完全相同（如你提供的範例），則不重複顯示在角標上
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
        # 移除不可見控制字元，保留合法 HTML 實體避免破壞 DOM 結構
        return re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', html_content)

    def isVideoFormat(self, url):
        return any(fmt in url for fmt in ['.m3u8', '.mp4', '.avi', '.mkv', '.flv', '.webm'])

    def manualVideoCheck(self):
        return True

    def localProxy(self, param):
        return {}

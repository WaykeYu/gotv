# -*- coding: utf-8 -*-
import json
import re
import sys
import urllib.parse
from bs4 import BeautifulSoup
import requests

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    host = 'https://4k01.pianku.online'

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            ' (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        ),
        'Referer': 'https://4k01.pianku.online/',
        'Accept-Language': 'zh-TW,zh;q=0.9,zh-CN;q=0.8,en;q=0.7',
    }

    # 記錄該網站實際使用的分類路徑前綴 (預設 /vodshow/)
    show_prefix = '/vodshow/'

    def getName(self):
        return '片庫'

    def init(self, extend=''):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        result = {}
        html = ''
        try:
            rsp = requests.get(self.host, headers=self.headers, timeout=12)
            rsp.encoding = 'utf-8'
            html = rsp.text
        except Exception:
            pass

        # 1. 自動從網頁導覽列抓取真實分類與 ID，若抓不到則使用預設值
        classes = self._parse_classes(html) if html else []
        if not classes:
            classes = [
                {'type_name': '電影', 'type_id': '1'},
                {'type_name': '連續劇', 'type_id': '2'},
                {'type_name': '綜藝', 'type_id': '3'},
                {'type_name': '動漫', 'type_id': '4'},
                {'type_name': '紀錄片', 'type_id': '5'},
                {'type_name': '4K專區', 'type_id': '6'},
            ]
        result['class'] = classes

        # 2. 篩選條件
        filters = {}
        years = [
            {'n': '全部', 'v': ''},
            {'n': '2026', 'v': '2026'},
            {'n': '2025', 'v': '2025'},
            {'n': '2024', 'v': '2024'},
            {'n': '2023', 'v': '2023'},
            {'n': '2022', 'v': '2022'},
            {'n': '2021', 'v': '2021'},
            {'n': '2020', 'v': '2020'},
            {'n': '更早', 'v': '2010'},
        ]
        areas = [
            {'n': '全部', 'v': ''},
            {'n': '大陸', 'v': '大陸'},
            {'n': '香港', 'v': '香港'},
            {'n': '台灣', 'v': '台灣'},
            {'n': '美國', 'v': '美國'},
            {'n': '韓國', 'v': '韓國'},
            {'n': '日本', 'v': '日本'},
            {'n': '英國', 'v': '英國'},
            {'n': '泰國', 'v': '泰國'},
        ]
        sorts = [
            {'n': '按時間', 'v': 'time'},
            {'n': '按人氣', 'v': 'hits'},
            {'n': '按評分', 'v': 'score'},
        ]
        default_cates = [
            {'n': '全部', 'v': ''},
            {'n': '動作', 'v': '動作'},
            {'n': '喜劇', 'v': '喜劇'},
            {'n': '愛情', 'v': '愛情'},
            {'n': '科幻', 'v': '科幻'},
            {'n': '恐怖', 'v': '恐怖'},
            {'n': '劇情', 'v': '劇情'},
            {'n': '懸疑', 'v': '懸疑'},
        ]

        for cls in classes:
            cid = cls['type_id']
            filters[cid] = [
                {'key': 'class', 'name': '類型', 'value': default_cates},
                {'key': 'area', 'name': '地區', 'value': areas},
                {'key': 'year', 'name': '年份', 'value': years},
                {'key': 'by', 'name': '排序', 'value': sorts},
            ]
        result['filters'] = filters

        # 3. 解析首頁推薦片單
        result['list'] = self._parse_vod_list(html) if html else []
        return result

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        area = urllib.parse.quote(extend.get('area', ''))
        by = extend.get('by', 'time')
        vod_class = urllib.parse.quote(extend.get('class', ''))
        year = extend.get('year', '')

        # 支援無篩選條件時直接訪問分類頁，有篩選時走篩選路由
        if not any([area, vod_class, year]) and by == 'time':
            url = (
                f'{self.host}/vodtype/{tid}-{pg}.html'
                if int(pg) > 1
                else f'{self.host}/vodtype/{tid}.html'
            )
        else:
            url = f'{self.host}{self.show_prefix}{tid}-{area}-{by}-{vod_class}-----{pg}---{year}.html'

        vod_list = []
        try:
            rsp = requests.get(url, headers=self.headers, timeout=12)
            rsp.encoding = 'utf-8'
            vod_list = self._parse_vod_list(rsp.text)

            # 若 /vodtype/ 路徑結構不同 (如 /type/ 或 /vodshow/)，自動切換備用路徑重試
            if not vod_list:
                alt_url = f'{self.host}{self.show_prefix}{tid}-{area}-{by}-{vod_class}-----{pg}---{year}.html'
                if alt_url != url:
                    rsp = requests.get(
                        alt_url, headers=self.headers, timeout=12
                    )
                    rsp.encoding = 'utf-8'
                    vod_list = self._parse_vod_list(rsp.text)
        except Exception:
            vod_list = []

        result['list'] = vod_list
        result['page'] = int(pg)
        result['pagecount'] = 999
        result['limit'] = 24
        result['total'] = 99999
        return result

    def detailContent(self, ids):
        vid = ids[0]
        # 直接使用片卡抓取到的完整相對路徑 (相容 /voddetail/、/detail/、/v/ 等各種路徑)
        if vid.startswith('http'):
            url = vid
        elif vid.startswith('/'):
            url = f'{self.host}{vid}'
        else:
            url = f'{self.host}/voddetail/{vid}.html'

        rsp = requests.get(url, headers=self.headers, timeout=12)
        rsp.encoding = 'utf-8'
        soup = BeautifulSoup(rsp.text, 'html.parser')

        title = ''
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)

        pic = ''
        for img in soup.find_all('img'):
            src = self._extract_img(img)
            if src and ('wsyzy.org' in src or 'ykimg.com' in src or 'upload' in src):
                pic = src
                break

        desc = ''
        desc_tag = soup.select_one(
            '.module-info-introduction-content, .vod_content, .detail-sketch, .stui-content__desc'
        )
        if desc_tag:
            desc = desc_tag.get_text(strip=True)

        play_from = []
        play_url = []

        tabs = soup.select(
            '.module-tab-items-box .module-tab-item, .nav-tabs li, .play-tab li, .stui-vodlist__head h3'
        )
        lists = soup.select(
            '.module-play-list-content, .stui-content__playlist, .myui-content__list'
        )

        if tabs and lists and len(tabs) == len(lists):
            for tab, plist in zip(tabs, lists):
                tab_name = tab.get_text(strip=True)
                ep_links = []
                for a in plist.find_all('a'):
                    ep_name = a.get_text(strip=True)
                    ep_href = a.get('href', '')
                    if ep_name and ep_href:
                        ep_links.append(f'{ep_name}${ep_href}')
                if ep_links:
                    play_from.append(tab_name)
                    play_url.append('#'.join(ep_links))
        else:
            # 備用：自動收集所有播放連結 (包含 play 關鍵字)
            play_from.append('預設線路')
            ep_links = []
            for a in soup.find_all('a', href=re.compile(r'play', re.I)):
                ep_name = a.get_text(strip=True)
                ep_href = a.get('href', '')
                if (
                    ep_name
                    and ep_href
                    and ep_href.endswith('.html')
                    and len(ep_name) < 20
                ):
                    ep_links.append(f'{ep_name}${ep_href}')
            play_url.append('#'.join(ep_links))

        vod = {
            'vod_id': vid,
            'vod_name': title,
            'vod_pic': pic,
            'vod_content': desc,
            'vod_play_from': '$$$'.join(play_from),
            'vod_play_url': '$$$'.join(play_url),
        }
        return {'list': [vod]}

    def searchContent(self, key, quick, pg='1'):
        encoded_key = urllib.parse.quote(key)
        # 嘗試常見蘋果CMS搜尋路徑
        search_urls = [
            f'{self.host}/vodsearch/{encoded_key}----------{pg}---.html',
            f'{self.host}/vodsearch/-------------.html?wd={encoded_key}',
            f'{self.host}/search.php?searchword={encoded_key}',
        ]
        for url in search_urls:
            try:
                rsp = requests.get(url, headers=self.headers, timeout=10)
                rsp.encoding = 'utf-8'
                vod_list = self._parse_vod_list(rsp.text)
                if vod_list:
                    return {'list': vod_list}
            except Exception:
                continue
        return {'list': []}

    def playerContent(self, flag, id, vipFlags):
        play_page_url = (
            f'{self.host}{id}' if not id.startswith('http') else id
        )
        result = {'parse': 0, 'playUrl': '', 'url': '', 'header': ''}

        try:
            rsp = requests.get(play_page_url, headers=self.headers, timeout=12)
            rsp.encoding = 'utf-8'
            html = rsp.text

            # 提取 player_aaaa 內的真實影片網址
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html, re.S)
            if m:
                player_data = json.loads(m.group(1))
                raw_url = player_data.get('url', '')

                if player_data.get('encrypt') == 1:
                    raw_url = urllib.parse.unquote(raw_url)
                elif player_data.get('encrypt') == 2:
                    import base64

                    raw_url = urllib.parse.unquote(
                        base64.b64decode(raw_url).decode('utf-8')
                    )

                if raw_url:
                    result['url'] = raw_url
                    result['parse'] = 0
                    result['header'] = json.dumps({
                        'User-Agent': self.headers['User-Agent'],
                        'Referer': '',
                    })
                    return result

            # 備用正則：直接匹配 .m3u8 網址
            m3u8_match = re.search(
                r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)', html
            )
            if m3u8_match:
                result['url'] = m3u8_match.group(1).replace('\\/', '/')
                result['parse'] = 0
                result['header'] = json.dumps({
                    'User-Agent': self.headers['User-Agent'],
                    'Referer': '',
                })
                return result

        except Exception:
            pass

        result['parse'] = 1
        result['url'] = play_page_url
        return result

    # --- 核心輔助解析函式 ---
    def _parse_classes(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        classes = []
        seen = set()
        # 匹配 /vodtype/1.html 或 /type/1.html 等分類連結
        for a in soup.find_all(
            'a', href=re.compile(r'/(?:vodtype|type|vodshow)/(\d+)')
        ):
            href = a.get('href', '')
            m = re.search(r'/(?:vodtype|type|vodshow)/(\d+)', href)
            name = a.get_text(strip=True)
            if m and name and 1 <= len(name) <= 6:
                tid = m.group(1)
                if tid not in seen and name not in ['首頁', '首页', '更多', '全部']:
                    seen.add(tid)
                    classes.append({'type_name': name, 'type_id': tid})
        return classes

    def _parse_vod_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        vod_list = []
        seen_hrefs = set()

        # 通用片卡解析：直接尋找所有包含 <img> 的 <a> 標籤
        for a in soup.find_all('a', href=True):
            href = a.get('href', '').strip()
            # 排除空連結、首頁、分類頁、播放頁與外部連結
            if (
                not href
                or href in ['/', '#']
                or href.startswith('javascript')
                or any(
                    x in href
                    for x in ['/vodtype/', '/vodshow/', '/vodplay/', '/topic/', '/art/']
                )
            ):
                continue

            img = a.find('img')
            if not img:
                continue

            pic = self._extract_img(img)
            # 過濾掉沒有圖片或非海報的小圖標 (logo/icon)
            if not pic or any(
                k in pic.lower() for k in ['logo', 'icon', 'avatar', 'qr', 'ad']
            ):
                continue

            if href in seen_hrefs:
                continue

            # 多層級尋找片名 (因應新版標籤沒有 alt 屬性的狀況)
            title = (
                a.get('title')
                or img.get('alt')
                or img.get('title')
                or ''
            ).strip()

            # 若 <a> 和 <img> 都沒有 title/alt，往卡片內部或父容器的標題元素尋找
            if not title:
                title_el = a.select_one(
                    '.title, .name, .module-poster-item-title, h3, h4, p, span'
                )
                if title_el:
                    title = title_el.get_text(strip=True)

            if not title and a.parent:
                # 尋找同卡片區塊內的下一個文字連結或標題標籤
                for sibling_a in a.parent.find_all('a', href=href):
                    txt = sibling_a.get_text(strip=True)
                    if txt:
                        title = txt
                        break
                if not title:
                    p_title = a.parent.select_one(
                        '.title, .name, .module-poster-item-title, h3, h4'
                    )
                    if p_title:
                        title = p_title.get_text(strip=True)

            # 尋找更新集數 / 評分 / 清晰度標籤
            remarks = ''
            container = a.parent if a.parent else a
            note_el = container.select_one(
                '.module-item-note, .pic-text, .text-right, .note, .tag'
            )
            if note_el:
                note_txt = note_el.get_text(strip=True)
                if note_txt and note_txt != title:
                    remarks = note_txt

            if title:
                seen_hrefs.add(href)
                vod_list.append({
                    'vod_id': href,  # 直接存完整相對路徑，避免詳情頁路徑拼錯
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remarks,
                })

        return vod_list

    def _extract_img(self, img_tag):
        for attr in ['data-original', 'data-src', 'data-echo', 'src']:
            val = img_tag.get(attr, '').strip()
            if val and '/load.gif' not in val and not val.startswith('data:image'):
                if val.startswith('//'):
                    return 'https:' + val
                elif val.startswith('/'):
                    return self.host + val
                return val
        return ''

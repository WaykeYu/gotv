# -*- coding: utf-8 -*-
import base64
import json
import os
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

    show_prefix = '/vodshow/'

    def _log(self, msg):
        try:
            log_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), 'pianku_debug.log'
            )
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(str(msg) + '\n')
        except Exception:
            pass

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
        except Exception as e:
            self._log(f'homeContent error: {e}')

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
            if src and (
                'wsyzy.org' in src or 'ykimg.com' in src or 'upload' in src
            ):
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
                    if ep_name and ep_href and not ep_href.startswith('javascript'):
                        ep_links.append(f'{ep_name}${ep_href}')
                if ep_links:
                    play_from.append(tab_name)
                    play_url.append('#'.join(ep_links))

        # 若上方標準容器沒抓到任何線路，全面掃描所有播放連結 (包含 /play/、/vodplay/、/v/ 等)
        if not play_url:
            ep_links = []
            seen_ep = set()
            for a in soup.find_all('a', href=True):
                ep_href = a.get('href', '').strip()
                ep_name = a.get_text(strip=True)
                if (
                    ep_name
                    and ep_href
                    and ep_href not in seen_ep
                    and not ep_href.startswith('javascript')
                    and any(k in ep_href.lower() for k in ['play', '/p/', 'nid='])
                    and len(ep_name) <= 25
                ):
                    seen_ep.add(ep_href)
                    ep_links.append(f'{ep_name}${ep_href}')
            if ep_links:
                play_from.append('預設線路')
                play_url.append('#'.join(ep_links))

        self._log(f'detailContent url={url}, play_from={play_from}, count={len(play_url)}')
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
        self._log(f'=== playerContent start: flag={flag}, id={id} ===')

        if '.m3u8' in id or '.mp4' in id:
            return self._build_video_response(id)

        play_page_url = (
            f'{self.host}{id}' if not id.startswith('http') else id
        )

        try:
            rsp = requests.get(play_page_url, headers=self.headers, timeout=12)
            rsp.encoding = 'utf-8'
            html = rsp.text

            # 1. 提取 player_aaaa / player_data
            m = re.search(
                r'(?:player_aaaa|player_data)\s*=\s*(\{.*?\})\s*[;<]',
                html,
                re.S,
            )
            if m:
                raw_json = m.group(1)
                self._log(f'player_aaaa found: {raw_json[:300]}')
                try:
                    data = json.loads(raw_json)
                    raw_url = data.get('url', '')
                    encrypt = data.get('encrypt', 0)
                    player_from = data.get('from', '')

                    if encrypt == 1:
                        raw_url = urllib.parse.unquote(raw_url)
                    elif encrypt == 2:
                        raw_url = urllib.parse.unquote(
                            base64.b64decode(raw_url).decode('utf-8')
                        )

                    self._log(
                        f'decoded url={raw_url}, from={player_from}, encrypt={encrypt}'
                    )

                    # 如果直接是影片直鏈
                    if '.m3u8' in raw_url or '.mp4' in raw_url:
                        return self._build_video_response(raw_url)

                    # 如果是解析器網址，請求該解析器頁面
                    if raw_url.startswith('http'):
                        sub_url = self._fetch_and_extract(
                            raw_url, referer=play_page_url
                        )
                        if sub_url:
                            return self._build_video_response(sub_url)

                    # 如果 raw_url 是一串加密字串 (非 http 開頭)，嘗試讀取該網站對應的播放器配置 /static/player/{from}.js
                    if raw_url and player_from:
                        js_url = f'{self.host}/static/player/{player_from}.js'
                        js_rsp = requests.get(
                            js_url, headers=self.headers, timeout=8
                        )
                        if js_rsp.status_code == 200:
                            self._log(
                                f'player js ({js_url}): {js_rsp.text[:300]}'
                            )
                            # 尋找播放器 JS 裡的解析接口網址 (如 src="https://.../?url=")
                            jx_m = re.search(
                                r'src=["\'](https?://[^"\']+?url=)["\']',
                                js_rsp.text,
                            )
                            if jx_m:
                                full_jx = jx_m.group(1) + urllib.parse.quote(
                                    raw_url
                                )
                                sub_url = self._fetch_and_extract(
                                    full_jx, referer=play_page_url
                                )
                                if sub_url:
                                    return self._build_video_response(sub_url)
                except Exception as e:
                    self._log(f'player_aaaa parse error: {e}')

            # 2. 直接在播放頁尋找 .m3u8 / .mp4 或 iframe
            direct_url = self._extract_stream_from_html(
                html, base_referer=play_page_url
            )
            if direct_url:
                return self._build_video_response(direct_url)

        except Exception as e:
            self._log(f'playerContent exception: {e}')

        self._log('playerContent failed to extract stream, fallback to parse=1')
        return {
            'parse': 1,
            'jx': 0,
            'playUrl': '',
            'url': play_page_url,
            'header': json.dumps(self.headers),
        }

    def _fetch_and_extract(self, target_url, referer=''):
        try:
            h = dict(self.headers)
            if referer:
                h['Referer'] = referer
            rsp = requests.get(target_url, headers=h, timeout=10)
            rsp.encoding = 'utf-8'
            return self._extract_stream_from_html(
                rsp.text, base_referer=target_url
            )
        except Exception as e:
            self._log(f'_fetch_and_extract error ({target_url}): {e}')
            return ''

    def _extract_stream_from_html(self, html, base_referer=''):
        # A. 正則直接提取 .m3u8 / .mp4
        found = self._regex_find_m3u8(html)
        if found:
            return found

        # B. 追蹤內部 iframe
        soup = BeautifulSoup(html, 'html.parser')
        for iframe in soup.find_all('iframe', src=True):
            src = iframe.get('src', '').strip()
            if not src or src.startswith('javascript'):
                continue
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = self.host + src

            parsed_qs = urllib.parse.parse_qs(
                urllib.parse.urlparse(src).query
            )
            for q_val in parsed_qs.values():
                if q_val and ('.m3u8' in q_val[0] or '.mp4' in q_val[0]):
                    return q_val[0]

            sub_found = self._fetch_and_extract(src, referer=base_referer)
            if sub_found:
                return sub_found

        return ''

    def _regex_find_m3u8(self, text):
        clean_text = text.replace('\\/', '/')
        patterns = [
            r'["\'](https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*)["\']',
            r'["\'](https?://[^"\'\s<>]+\.mp4[^"\'\s<>]*)["\']',
            r'(https?://[^\s"\'<>]+\.m3u8[^\s"\'<>]*)',
        ]
        for pat in patterns:
            for url in re.findall(pat, clean_text):
                if 'url=http' in url:
                    real = url.split('url=', 1)[1]
                    return urllib.parse.unquote(real)
                return url

        for b64_str in re.findall(
            r'["\'](aHR0c[A-Za-z0-9+/=]{20,})["\']', clean_text
        ):
            try:
                decoded = base64.b64decode(b64_str).decode('utf-8')
                if '.m3u8' in decoded or '.mp4' in decoded:
                    return decoded
            except Exception:
                continue
        return ''

    def _build_video_response(self, stream_url):
        self._log(f'SUCCESS stream_url={stream_url}')
        return {
            'parse': 0,
            'playUrl': '',
            'url': stream_url,
            'header': json.dumps({
                'User-Agent': self.headers['User-Agent'],
                'Referer': '',
            }),
        }

    # --- 輔助解析函式 ---
    def _parse_classes(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        classes = []
        seen = set()
        for a in soup.find_all(
            'a', href=re.compile(r'/(?:vodtype|type|vodshow)/(\d+)')
        ):
            href = a.get('href', '')
            m = re.search(r'/(?:vodtype|type|vodshow)/(\d+)', href)
            name = a.get_text(strip=True)
            if m and name and 1 <= len(name) <= 6:
                tid = m.group(1)
                if tid not in seen and name not in [
                    '首頁',
                    '首页',
                    '更多',
                    '全部',
                ]:
                    seen.add(tid)
                    classes.append({'type_name': name, 'type_id': tid})
        return classes

    def _parse_vod_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        vod_list = []
        seen_hrefs = set()

        for a in soup.find_all('a', href=True):
            href = a.get('href', '').strip()
            if (
                not href
                or href in ['/', '#']
                or href.startswith('javascript')
                or any(
                    x in href
                    for x in [
                        '/vodtype/',
                        '/vodshow/',
                        '/vodplay/',
                        '/topic/',
                        '/art/',
                    ]
                )
            ):
                continue

            img = a.find('img')
            if not img:
                continue

            pic = self._extract_img(img)
            if not pic or any(
                k in pic.lower()
                for k in ['logo', 'icon', 'avatar', 'qr', 'ad']
            ):
                continue

            if href in seen_hrefs:
                continue

            title = (
                a.get('title')
                or img.get('alt')
                or img.get('title')
                or ''
            ).strip()

            if not title:
                title_el = a.select_one(
                    '.title, .name, .module-poster-item-title, h3, h4, p, span'
                )
                if title_el:
                    title = title_el.get_text(strip=True)

            if not title and a.parent:
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
                    'vod_id': href,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remarks,
                })

        return vod_list

    def _extract_img(self, img_tag):
        for attr in ['data-original', 'data-src', 'data-echo', 'src']:
            val = img_tag.get(attr, '').strip()
            if (
                val
                and '/load.gif' not in val
                and not val.startswith('data:image')
            ):
                if val.startswith('//'):
                    return 'https:' + val
                elif val.startswith('/'):
                    return self.host + val
                return val
        return ''

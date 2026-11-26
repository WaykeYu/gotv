# -*- coding: utf-8 -*-
import base64
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
        'Accept-Language': 'zh-CN,zh;q=0.9,zh-TW;q=0.8,en;q=0.7',
    }

    # 預設篩選路由模板 (會在 homeContent 自動修正為網站真實前綴)
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

        # 1. 分類完整
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

        # 2. 篩選條件 (自動從網站抓取真實篩選結構與簡體參數值)
        filters = {}
        for idx, cls in enumerate(classes):
            cid = cls['type_id']
            site_filters = self._scrape_filters_from_site(cid)
            if site_filters:
                filters[cid] = site_filters
            elif idx > 0 and classes[0]['type_id'] in filters:
                filters[cid] = filters[classes[0]['type_id']]
            else:
                filters[cid] = self._get_default_filters()

        result['filters'] = filters
        result['list'] = self._parse_vod_list(html) if html else []
        return result

    def _get_default_filters(self):
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
            {'n': '大陸', 'v': '大陆'},
            {'n': '香港', 'v': '香港'},
            {'n': '台灣', 'v': '台湾'},
            {'n': '美國', 'v': '美国'},
            {'n': '韓國', 'v': '韩国'},
            {'n': '日本', 'v': '日本'},
            {'n': '英國', 'v': '英国'},
            {'n': '泰國', 'v': '泰国'},
        ]
        sorts = [
            {'n': '按時間', 'v': 'time'},
            {'n': '按人氣', 'v': 'hits'},
            {'n': '按評分', 'v': 'score'},
        ]
        cates = [
            {'n': '全部', 'v': ''},
            {'n': '動作', 'v': '动作'},
            {'n': '喜劇', 'v': '喜剧'},
            {'n': '愛情', 'v': '爱情'},
            {'n': '科幻', 'v': '科幻'},
            {'n': '恐怖', 'v': '恐怖'},
            {'n': '劇情', 'v': '剧情'},
            {'n': '戰爭', 'v': '战争'},
            {'n': '犯罪', 'v': '犯罪'},
            {'n': '懸疑', 'v': '悬疑'},
        ]
        return [
            {'key': 'class', 'name': '類型', 'value': cates},
            {'key': 'area', 'name': '地區', 'value': areas},
            {'key': 'year', 'name': '年份', 'value': years},
            {'key': 'by', 'name': '排序', 'value': sorts},
        ]

    def _scrape_filters_from_site(self, tid):
        try:
            for prefix in ['/vodshow/', '/show/']:
                u = f'{self.host}{prefix}{tid}-----------.html'
                rsp = requests.get(u, headers=self.headers, timeout=8)
                if rsp.status_code == 200 and f'{prefix}{tid}-' in rsp.text:
                    self.show_prefix = prefix
                    rsp.encoding = 'utf-8'
                    soup = BeautifulSoup(rsp.text, 'html.parser')

                    groups_data = {'class': [], 'area': [], 'year': [], 'by': []}
                    seen_vals = {'class': set(), 'area': set(), 'year': set(), 'by': set()}

                    for a in soup.find_all(
                        'a', href=re.compile(re.escape(prefix) + str(tid) + r'-')
                    ):
                        txt = a.get_text(strip=True)
                        href = a.get('href', '')
                        if not txt or len(txt) > 10 or txt in ['全部', '不限']:
                            continue
                        seg = href.split('/')[-1].replace('.html', '').split('-')
                        if len(seg) >= 12:
                            # seg[1]=area, seg[2]=by, seg[3]=class, seg[11]=year
                            if seg[1] and seg[1] not in seen_vals['area']:
                                seen_vals['area'].add(seg[1])
                                groups_data['area'].append(
                                    {'n': txt, 'v': urllib.parse.unquote(seg[1])}
                                )
                            elif seg[3] and seg[3] not in seen_vals['class']:
                                seen_vals['class'].add(seg[3])
                                groups_data['class'].append(
                                    {'n': txt, 'v': urllib.parse.unquote(seg[3])}
                                )
                            elif seg[11] and seg[11] not in seen_vals['year']:
                                seen_vals['year'].add(seg[11])
                                groups_data['year'].append(
                                    {'n': txt, 'v': urllib.parse.unquote(seg[11])}
                                )
                            elif (
                                seg[2] in ['time', 'hits', 'score']
                                and seg[2] not in seen_vals['by']
                            ):
                                seen_vals['by'].add(seg[2])
                                groups_data['by'].append({'n': txt, 'v': seg[2]})

                    res = []
                    name_map = [
                        ('class', '類型'),
                        ('area', '地區'),
                        ('year', '年份'),
                        ('by', '排序'),
                    ]
                    for k, label in name_map:
                        if groups_data[k]:
                            opts = [{'n': '全部', 'v': ''}] + groups_data[k]
                            res.append({'key': k, 'name': label, 'value': opts})
                    if res:
                        return res
        except Exception:
            pass
        return []

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        area = urllib.parse.quote(extend.get('area', ''))
        by = extend.get('by', 'time')
        vod_class = urllib.parse.quote(extend.get('class', ''))
        year = extend.get('year', '')

        has_filter = any([area, vod_class, year]) or by != 'time'

        if not has_filter:
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

            # 若 /vodtype/ 不存在或無結果，自動嘗試另一種前綴路由
            if not vod_list:
                alt_prefix = '/show/' if self.show_prefix == '/vodshow/' else '/vodshow/'
                for try_url in [
                    f'{self.host}{self.show_prefix}{tid}-{area}-{by}-{vod_class}-----{pg}---{year}.html',
                    f'{self.host}{alt_prefix}{tid}-{area}-{by}-{vod_class}-----{pg}---{year}.html',
                ]:
                    if try_url == url:
                        continue
                    rsp = requests.get(try_url, headers=self.headers, timeout=12)
                    rsp.encoding = 'utf-8'
                    vod_list = self._parse_vod_list(rsp.text)
                    if vod_list:
                        break
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

        # 精準提取多線路名稱與對應集數列表
        tabs = soup.select(
            '.module-tab-items-box .module-tab-item, .nav-tabs li, .play-tab li, .stui-vodlist__head h3'
        )
        lists = soup.select(
            '.module-play-list-content, .stui-content__playlist, .myui-content__list, .module-play-list'
        )

        if tabs and lists and len(tabs) == len(lists):
            for tab, plist in zip(tabs, lists):
                tab_name = tab.get_text(strip=True)
                ep_links = []
                for a in plist.find_all('a', href=True):
                    ep_name = a.get_text(strip=True)
                    ep_href = a.get('href', '')
                    if (
                        ep_name
                        and ep_href
                        and not ep_href.startswith('javascript')
                    ):
                        ep_links.append(f'{ep_name}${ep_href}')
                if ep_links:
                    play_from.append(tab_name)
                    play_url.append('#'.join(ep_links))
        elif lists:
            for idx, plist in enumerate(lists, 1):
                ep_links = []
                for a in plist.find_all('a', href=True):
                    ep_name = a.get_text(strip=True)
                    ep_href = a.get('href', '')
                    if (
                        ep_name
                        and ep_href
                        and not ep_href.startswith('javascript')
                    ):
                        ep_links.append(f'{ep_name}${ep_href}')
                if ep_links:
                    play_from.append(f'線路{idx}')
                    play_url.append('#'.join(ep_links))

        if not play_url:
            # 依線路編號 (-1-1, -2-1) 自動分組
            grouped = {}
            for a in soup.find_all('a', href=re.compile(r'/vodplay/\d+-\d+-\d+\.html')):
                ep_href = a.get('href', '').strip()
                ep_name = a.get_text(strip=True)
                m_sid = re.search(r'/vodplay/\d+-(\d+)-\d+\.html', ep_href)
                sid = m_sid.group(1) if m_sid else '1'
                if ep_name and len(ep_name) <= 25:
                    grouped.setdefault(sid, []).append(f'{ep_name}${ep_href}')
            for sid, links in grouped.items():
                play_from.append(f'線路{sid}')
                play_url.append('#'.join(links))

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
        if '.m3u8' in id or '.mp4' in id:
            return self._build_video_response(id)

        play_page_url = (
            f'{self.host}{id}' if not id.startswith('http') else id
        )

        raw_url = ''
        player_from = ''

        try:
            rsp = requests.get(play_page_url, headers=self.headers, timeout=12)
            rsp.encoding = 'utf-8'
            html = rsp.text

            # 1. 提取 player_aaaa 變數 (處理跳脫斜線 \/ )
            m = re.search(
                r'(?:player_aaaa|player_data)\s*=\s*(\{.*?\})\s*[;<]',
                html,
                re.S,
            )
            if m:
                data = json.loads(m.group(1))
                raw_url = data.get('url', '').replace('\\/', '/')
                encrypt = data.get('encrypt', 0)
                player_from = data.get('from', '')

                if encrypt == 1:
                    raw_url = urllib.parse.unquote(raw_url)
                elif encrypt == 2:
                    raw_url = urllib.parse.unquote(
                        base64.b64decode(raw_url).decode('utf-8')
                    )

                # A. 如果已經是直鏈 (.m3u8 / .mp4)
                if '.m3u8' in raw_url or '.mp4' in raw_url:
                    return self._build_video_response(raw_url)

                # B. 核心修復：無論 raw_url 是否為 http (如 v.qq.com)，優先讀取網站的 /static/player/{from}.js 尋找其內建解析接口！
                if raw_url and player_from:
                    stream_from_js = self._resolve_via_player_js(
                        player_from, raw_url, play_page_url
                    )
                    if stream_from_js:
                        return self._build_video_response(stream_from_js)

                # C. 若沒有 player_from，但 raw_url 是第三方解析器網址 (非官方視頻網站)
                official_domains = [
                    'v.qq.com',
                    'iqiyi.com',
                    'youku.com',
                    'mgtv.com',
                    'bilibili.com',
                    'sohu.com',
                    'le.com',
                ]
                if raw_url.startswith('http') and not any(
                    d in raw_url for d in official_domains
                ):
                    sub_url = self._fetch_and_extract(
                        raw_url, referer=play_page_url
                    )
                    if sub_url:
                        return self._build_video_response(sub_url)

            # 2. 檢查播放頁內是否有隱藏 iframe 或直鏈
            direct_url = self._extract_stream_from_html(
                html, base_referer=play_page_url
            )
            if direct_url:
                return self._build_video_response(direct_url)

        except Exception:
            pass

        # 3. 終極兜底：如果站內解析器全數無法在後端解出，將真實的官採連結 (如 v.qq.com) 加上 jx: 1 交給 Yumilo 設定的「首選解析接口」播放！
        target_for_jx = raw_url if raw_url.startswith('http') else play_page_url
        return {
            'parse': 1,
            'jx': 1 if raw_url.startswith('http') else 0,
            'playUrl': '',
            'url': target_for_jx,
            'header': json.dumps(self.headers),
        }

    def _resolve_via_player_js(self, player_from, video_url, referer):
        """讀取 MacCMS /static/player/{from}.js 並呼叫其內建解析接口"""
        js_candidates = [
            f'{self.host}/static/player/{player_from}.js',
            f'{self.host}/static/js/playerconfig.js',
        ]
        for js_url in js_candidates:
            try:
                js_rsp = requests.get(js_url, headers=self.headers, timeout=8)
                if js_rsp.status_code != 200:
                    continue
                js_text = js_rsp.text.replace('\\/', '/')

                # 從 JS 中尋找解析接口前綴 (例如: src="https://jx.xxx.com/?url=" 或 "parse":"https://...")
                jx_urls = re.findall(
                    r'(https?://[^\s"\'<>]+?(?:url=|vid=|id=|v=))', js_text
                )
                for jx_base in jx_urls:
                    # 排除自身網域的無效跳轉
                    if self.host in jx_base and 'url=' not in jx_base:
                        continue
                    full_jx = jx_base + urllib.parse.quote(video_url, safe='')
                    extracted = self._fetch_and_extract(full_jx, referer=referer)
                    if extracted:
                        return extracted
            except Exception:
                continue
        return ''

    def _fetch_and_extract(self, target_url, referer=''):
        try:
            h = dict(self.headers)
            if referer:
                h['Referer'] = referer
            rsp = requests.get(target_url, headers=h, timeout=10)
            rsp.encoding = 'utf-8'
            # 若回傳的是 JSON 格式 (許多解析接口直接回傳 {"code":200,"url":"https://...m3u8"})
            try:
                jdata = rsp.json()
                for k in ['url', 'data', 'vurl', 'playurl']:
                    val = jdata.get(k)
                    if isinstance(val, str) and (
                        '.m3u8' in val or '.mp4' in val
                    ):
                        return val
                    elif isinstance(val, dict) and isinstance(
                        val.get('url'), str
                    ):
                        if '.m3u8' in val['url'] or '.mp4' in val['url']:
                            return val['url']
            except Exception:
                pass

            return self._extract_stream_from_html(
                rsp.text, base_referer=target_url
            )
        except Exception:
            return ''

    def _extract_stream_from_html(self, html, base_referer=''):
        found = self._regex_find_m3u8(html)
        if found:
            return found

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
        return {
            'parse': 0,
            'playUrl': '',
            'url': stream_url,
            'header': json.dumps({
                'User-Agent': self.headers['User-Agent'],
                'Referer': '',
            }),
        }

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

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
            ' (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
        'Referer': 'https://4k01.pianku.online/',
    }

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
        # 1. 完整分類 (對應常見蘋果CMS標準ID，若網站ID不同可依實際網址調整)
        classes = [
            {'type_name': '電影', 'type_id': '1'},
            {'type_name': '連續劇', 'type_id': '2'},
            {'type_name': '綜藝', 'type_id': '3'},
            {'type_name': '動漫', 'type_id': '4'},
            {'type_name': '紀錄片', 'type_id': '5'},
            {'type_name': '4K專區', 'type_id': '6'},
        ]
        result['class'] = classes

        # 2. 篩選條件 (包含類型、地區、年份、排序)
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

        # 各分類專屬劇情類型
        cates_map = {
            '1': [
                '全部',
                '動作片',
                '喜劇片',
                '愛情片',
                '科幻片',
                '恐怖片',
                '劇情片',
                '戰爭片',
                '犯罪片',
                '懸疑片',
            ],
            '2': [
                '全部',
                '國產劇',
                '港台劇',
                '日韓劇',
                '歐美劇',
                '海外劇',
                '古裝',
                '都市',
                '懸疑',
            ],
            '3': ['全部', '大陸綜藝', '港台綜藝', '日韓綜藝', '歐美綜藝'],
            '4': ['全部', '國產動漫', '日韓動漫', '歐美動漫', '劇場版'],
            '5': ['全部', '自然', '歷史', '人文', '科技', '社會'],
            '6': ['全部', '4K電影', '4K劇集', '4K動漫', '杜比視界'],
        }

        for cid, c_list in cates_map.items():
            cate_opts = [
                {'n': c, 'v': '' if c == '全部' else c} for c in c_list
            ]
            filters[cid] = [
                {'key': 'class', 'name': '類型', 'value': cate_opts},
                {'key': 'area', 'name': '地區', 'value': areas},
                {'key': 'year', 'name': '年份', 'value': years},
                {'key': 'by', 'name': '排序', 'value': sorts},
            ]

        result['filters'] = filters

        # 獲取首頁推薦片單
        try:
            rsp = requests.get(self.host, headers=self.headers, timeout=10)
            rsp.encoding = 'utf-8'
            result['list'] = self._parse_vod_list(rsp.text)
        except Exception:
            result['list'] = []

        return result

    def homeVideoContent(self):
        return {'list': []}

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        # 組合蘋果CMS標準篩選路徑: /vodshow/{id}-{area}-{by}-{class}-----{pg}---{year}.html
        area = urllib.parse.quote(extend.get('area', ''))
        by = extend.get('by', 'time')
        vod_class = urllib.parse.quote(extend.get('class', ''))
        year = extend.get('year', '')

        url = f'{self.host}/vodshow/{tid}-{area}-{by}-{vod_class}-----{pg}---{year}.html'

        try:
            rsp = requests.get(url, headers=self.headers, timeout=10)
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
        url = (
            f'{self.host}/voddetail/{vid}.html'
            if not vid.startswith('http')
            else vid
        )

        rsp = requests.get(url, headers=self.headers, timeout=10)
        rsp.encoding = 'utf-8'
        soup = BeautifulSoup(rsp.text, 'html.parser')

        # 標題與海報
        title = ''
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)

        pic = ''
        img_tag = soup.select_one(
            '.module-info-poster img, .lazyload, img[referrerpolicy="no-referrer"]'
        )
        if img_tag:
            pic = self._extract_img(img_tag)

        # 簡介與資訊
        desc = ''
        desc_tag = soup.select_one(
            '.module-info-introduction-content, .vod_content, .detail-sketch'
        )
        if desc_tag:
            desc = desc_tag.get_text(strip=True)

        # 解析播放線路與集數
        play_from = []
        play_url = []

        # 適配常見播放器 Tab 結構
        tabs = soup.select(
            '.module-tab-items-box .module-tab-item, .nav-tabs li, .play-tab li'
        )
        lists = soup.select(
            '.module-play-list-content, .stui-content__playlist, .myui-content__list'
        )

        if tabs and lists and len(tabs) == len(lists):
            for tab, plist in zip(tabs, lists):
                tab_name = tab.get_text(strip=True)
                play_from.append(tab_name)
                ep_links = []
                for a in plist.find_all('a'):
                    ep_name = a.get_text(strip=True)
                    ep_href = a.get('href', '')
                    ep_links.append(f'{ep_name}${ep_href}')
                play_url.append('#'.join(ep_links))
        else:
            # 備用解析：直接抓取所有包含 /vodplay/ 的連結
            play_from.append('預設線路')
            ep_links = []
            for a in soup.find_all('a', href=re.compile(r'/vodplay/')):
                ep_name = a.get_text(strip=True)
                ep_href = a.get('href', '')
                if ep_name and ep_href:
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
        url = f'{self.host}/vodsearch/{encoded_key}----------{pg}---.html'

        try:
            rsp = requests.get(url, headers=self.headers, timeout=10)
            rsp.encoding = 'utf-8'
            vod_list = self._parse_vod_list(rsp.text)
        except Exception:
            vod_list = []

        return {'list': vod_list}

    def playerContent(self, flag, id, vipFlags):
        play_page_url = (
            f'{self.host}{id}' if not id.startswith('http') else id
        )
        result = {'parse': 0, 'playUrl': '', 'url': '', 'header': ''}

        try:
            rsp = requests.get(play_page_url, headers=self.headers, timeout=10)
            rsp.encoding = 'utf-8'
            html = rsp.text

            # 4. 提取 player_aaaa 內的真實影片網址 (包含 sviptq.com / .m3u8 等參數網址)
            m = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', html, re.S)
            if m:
                player_data = json.loads(m.group(1))
                raw_url = player_data.get('url', '')

                # 處理 URL 編碼或 Base64 編碼
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
                    # 針對 sviptq.com / ykimg 等 CDN 設定播放器標頭 (不帶 Referer 或帶正確 UA)
                    result['header'] = json.dumps({
                        'User-Agent': self.headers['User-Agent'],
                        'Referer': '',
                    })
                    return result

            # 備用正則：直接匹配網頁中出現的 .m3u8 網址 (如範例中的 sviptq.com 網址)
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

        # 若無法直接提取直鏈，交由 TVBox 內建嗅探器處理
        result['parse'] = 1
        result['url'] = play_page_url
        return result

    # --- 輔助解析函式 ---
    def _parse_vod_list(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        vod_list = []
        seen_ids = set()

        # 尋找所有指向 /voddetail/ 的卡片連結
        for a in soup.find_all('a', href=re.compile(r'/voddetail/(\d+)\.html')):
            href = a.get('href', '')
            id_match = re.search(r'/voddetail/(\d+)\.html', href)
            if not id_match:
                continue

            vid = id_match.group(1)
            if vid in seen_ids:
                continue

            # 尋找內部的 img 標籤 (匹配條件3: <img src="http://m.ykimg.com/..." alt="巨人" referrerpolicy="no-referrer" ...>)
            img = a.find('img')
            if not img and a.parent:
                img = a.parent.find('img')

            if not img:
                continue

            pic = self._extract_img(img)
            title = (
                img.get('alt')
                or a.get('title')
                or a.get_text(strip=True)
                or ''
            )

            # 尋找更新狀態/清晰度標籤 (如 HD, 更新至第X集)
            remarks = ''
            parent_box = a.parent if a.parent else a
            note_tag = parent_box.select_one(
                '.module-item-note, .pic-text, .text-right, span'
            )
            if note_tag and note_tag.get_text(strip=True) != title:
                remarks = note_tag.get_text(strip=True)

            if title:
                seen_ids.add(vid)
                vod_list.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': remarks,
                })

        return vod_list

    def _extract_img(self, img_tag):
        # 優先讀取真實圖片屬性，避開 /load.gif 佔位圖
        for attr in ['data-original', 'data-src', 'src']:
            val = img_tag.get(attr, '').strip()
            if val and '/load.gif' not in val:
                if val.startswith('//'):
                    return 'https:' + val
                elif val.startswith('/'):
                    return self.host + val
                return val
        return ''

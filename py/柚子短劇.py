# -*- coding: utf-8 -*-
import sys
import re
import json
import requests
from bs4 import BeautifulSoup

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "柚子短劇"

    def init(self, extend=""):
        self.host = "https://youzidj.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.host + "/"
        }

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|flv|mkv)(\?|$)', url, re.I))

    def manualVideoCheck(self):
        return False

    # 1. 首頁分類與篩選器設定
    def homeContent(self, filter):
        result = {}
        classes = [
            {"type_id": "1", "type_name": "熱門短劇"},
            {"type_id": "2", "type_name": "甜寵虐戀"},
            {"type_id": "3", "type_name": "戰神贅婿"},
            {"type_id": "4", "type_name": "重生逆襲"},
            {"type_id": "5", "type_name": "古裝穿越"}
        ]
        result['class'] = classes

        # 定義共用篩選條件（key 對應蘋果 CMS 的 URL 參數名）
        common_filters = [
            {
                "key": "area",
                "name": "地區",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "大陸", "v": "大陸"},
                    {"n": "台灣", "v": "台灣"},
                    {"n": "香港", "v": "香港"},
                    {"n": "韓國", "v": "韓國"},
                    {"n": "歐美", "v": "歐美"}
                ]
            },
            {
                "key": "year",
                "name": "年份",
                "value": [
                    {"n": "全部", "v": ""},
                    {"n": "2026", "v": "2026"},
                    {"n": "2025", "v": "2025"},
                    {"n": "2024", "v": "2024"},
                    {"n": "2023", "v": "2023"},
                    {"n": "更早", "v": "2022"}
                ]
            },
            {
                "key": "by",
                "name": "排序",
                "value": [
                    {"n": "最新更新", "v": "time"},
                    {"n": "最多播放", "v": "hits"},
                    {"n": "最高評分", "v": "score"}
                ]
            }
        ]

        # 將篩選器綁定到所有分類 ID 上
        filters = {}
        for item in classes:
            filters[item["type_id"]] = common_filters
        result['filters'] = filters

        try:
            resp = requests.get(self.host, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')
            result['list'] = self._parse_vod_list(soup)
        except Exception:
            result['list'] = []

        return result

    def homeVideoContent(self):
        return {}

    # 2. 分類列表（支援分頁與 extend 篩選參數）
    def categoryContent(self, tid, pg, filter, extend):
        result = {}

        # 從 extend 取得使用者點選的篩選值（若無則為空字串）
        area = requests.utils.quote(extend.get('area', ''))
        year = requests.utils.quote(extend.get('year', ''))
        by = extend.get('by', 'time')

        # 判斷是否有使用篩選條件
        if area or year or extend.get('by'):
            # 蘋果 CMS 標準篩選路由結構：
            # /vodshow/{id}-{area}-{by}-{class}-{lang}-{letter}---{page}---{year}.html
            url = f"{self.host}/vodshow/{tid}-{area}-{by}------{pg}---{year}.html"
        else:
            # 無篩選時走預設分類頁
            url = f"{self.host}/vodtype/{tid}-{pg}.html"

        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')
            videos = self._parse_vod_list(soup)
            result['list'] = videos
            result['page'] = int(pg)
            result['pagecount'] = 999
            result['limit'] = len(videos)
            result['total'] = 9999
        except Exception:
            result['list'] = []
        return result

    # 3. 影片詳情與選集列表
    def detailContent(self, ids):
        vid = ids[0]
        url = vid if vid.startswith('http') else f"{self.host}{vid}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')

            title_el = soup.select_one('h1')
            title = title_el.get_text(strip=True) if title_el else "未知標題"
            pic_el = soup.select_one('.module-item-pic img, .lazyload, img[data-original]')
            pic = ""
            if pic_el:
                pic = pic_el.get('data-original') or pic_el.get('data-src') or pic_el.get('src') or ""
                if pic.startswith('/'):
                    pic = self.host + pic

            desc_el = soup.select_one('.module-info-introduction-content, .vod_content, .detail-content')
            desc = desc_el.get_text(strip=True) if desc_el else ""

            play_from = []
            play_url = []
            tabs = soup.select('.module-tab-item, .nav-tabs li a')
            playlists = soup.select('.module-play-list-content, .stui-content__playlist')

            for idx, plist in enumerate(playlists):
                tab_name = tabs[idx].get_text(strip=True) if idx < len(tabs) else f"線路{idx + 1}"
                episodes = []
                for a in plist.select('a'):
                    ep_name = a.get_text(strip=True)
                    ep_href = a.get('href', '')
                    if ep_href:
                        episodes.append(f"{ep_name}${ep_href}")
                if episodes:
                    play_from.append(tab_name)
                    play_url.append("#".join(episodes))

            vod = {
                "vod_id": vid,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": desc,
                "vod_play_from": "$$$".join(play_from),
                "vod_play_url": "$$$".join(play_url)
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    # 4. 關鍵字搜尋
    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/vodsearch/-------------.html?wd={requests.utils.quote(key)}"
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'lxml')
            return {"list": self._parse_vod_list(soup)}
        except Exception:
            return {"list": []}

    # 5. 解析播放頁真實串流網址
    def playerContent(self, flag, id, vipFlags):
        play_page = id if id.startswith('http') else f"{self.host}{id}"
        try:
            resp = requests.get(play_page, headers=self.headers, timeout=10)
            resp.encoding = 'utf-8'
            html = resp.text

            match = re.search(r'player_aaaa\s*=\s*(\{.*?\})\s*</script>', html, re.S)
            if match:
                player_data = json.loads(match.group(1))
                real_url = player_data.get('url', '')
                if real_url:
                    return {
                        "parse": 0 if self.isVideoFormat(real_url) else 1,
                        "playUrl": "",
                        "url": real_url,
                        "header": json.dumps(self.headers)
                    }

            m3u8_match = re.search(r'(https?://[^\s"\'\\]+\.(?:m3u8|mp4)[^\s"\'\\]*)', html)
            if m3u8_match:
                real_url = m3u8_match.group(1).replace('\\/', '/')
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": real_url,
                    "header": json.dumps(self.headers)
                }
        except Exception:
            pass

        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page,
            "header": json.dumps(self.headers)
        }

    # 共用：解析列表卡片元素
    def _parse_vod_list(self, soup):
        videos = []
        items = soup.select('.module-poster-item, .module-item, .stui-vodlist__box')
        for item in items:
            a = item if item.name == 'a' else item.select_one('a')
            if not a:
                continue
            href = a.get('href', '')
            title = a.get('title') or (item.select_one('.module-poster-item-title, .title') and item.select_one('.module-poster-item-title, .title').get_text(strip=True)) or ""
            img = item.select_one('img')
            pic = ""
            if img:
                pic = img.get('data-original') or img.get('data-src') or img.get('src') or ""
                if pic.startswith('/'):
                    pic = self.host + pic
            remark_el = item.select_one('.module-item-note, .pic-text')
            remark = remark_el.get_text(strip=True) if remark_el else ""

            if href and title:
                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
        return videos

    def localProxy(self, param):
        return [200, "video/MP2T", "", {}]

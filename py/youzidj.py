# -*- coding: utf-8 -*-
import json
import re
import sys
import urllib.parse
from pyquery import PyQuery as pq
import requests

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "柚子短劇"

    def init(self, extend=""):
        self.host = "https://youzidj.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": self.host + "/"
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        # 定義首頁分類，需依網頁實際導覽列 ID 微調
        classes = [
            {"type_name": "短劇", "type_id": "1"},
            {"type_name": "爽劇", "type_id": "2"},
            {"type_name": "逆襲", "type_id": "3"},
            {"type_name": "甜寵", "type_id": "4"},
            {"type_name": "古裝", "type_id": "5"},
            {"type_name": "都市", "type_id": "6"}
        ]
        result = {"class": classes}
        try:
            res = self.session.get(self.host, timeout=8)
            res.encoding = "utf-8"
            result["list"] = self._parse_vod_list(res.text)
        except Exception as e:
            result["list"] = []
        return result

    def homeVideoContent(self):
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        # 常見 MacCMS 分類 URL 結構，若網頁不同請依實際網址修改
        url = f"{self.host}/vodtype/{tid}-{pg}.html"
        result = {
            "page": int(pg),
            "pagecount": 999,
            "limit": 20,
            "total": 9999,
            "list": []
        }
        try:
            res = self.session.get(url, timeout=8)
            res.encoding = "utf-8"
            result["list"] = self._parse_vod_list(res.text)
        except Exception:
            pass
        return result

    def detailContent(self, ids):
        vod_id = ids[0]
        url = vod_id if vod_id.startswith("http") else f"{self.host}{vod_id}"
        try:
            res = self.session.get(url, timeout=8)
            res.encoding = "utf-8"
            doc = pq(res.text)

            title = doc("h1").text().strip()
            pic = doc(".module-info-poster img").attr("data-original") or doc(".module-info-poster img").attr("src") or ""
            if pic and not pic.startswith("http"):
                pic = self.host + pic
            content = doc(".module-info-introduction-content").text().strip()

            # 解析播放線路名稱
            tabs = [item.text().strip() for item in doc(".module-tab-item").items()]
            if not tabs:
                tabs = ["預設線路"]

            # 解析各線路劇集列表
            play_lists = []
            for playlist_box in doc(".module-play-list-content").items():
                episodes = []
                for a in playlist_box("a").items():
                    ep_name = a.text().strip()
                    ep_url = a.attr("href")
                    if ep_url:
                        episodes.append(f"{ep_name}${ep_url}")
                if episodes:
                    play_lists.append("#".join(episodes))

            vod = {
                "vod_id": vod_id,
                "vod_name": title,
                "vod_pic": pic,
                "vod_content": content,
                "vod_play_from": "$$$".join(tabs[:len(play_lists)]),
                "vod_play_url": "$$$".join(play_lists)
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        encoded_key = urllib.parse.quote(key)
        url = f"{self.host}/vodsearch/{encoded_key}----------{pg}---.html"
        try:
            res = self.session.get(url, timeout=8)
            res.encoding = "utf-8"
            return {"list": self._parse_vod_list(res.text, is_search=True)}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        play_page_url = id if id.startswith("http") else f"{self.host}{id}"
        try:
            res = self.session.get(play_page_url, timeout=8)
            res.encoding = "utf-8"
            # 優先正則提取 MacCMS 常見的 player_aaaa 變數中的直連地址
            match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\})\s*</script>', res.text, re.S)
            if match:
                player_data = json.loads(match.group(1))
                video_url = player_data.get("url", "")
                # 處理 URL 編碼或 Base64 編碼
                if player_data.get("encrypt") == 1:
                    video_url = urllib.parse.unquote(video_url)
                elif player_data.get("encrypt") == 2:
                    import base64
                    video_url = urllib.parse.unquote(base64.b64decode(video_url).decode("utf-8"))

                if video_url.startswith("http") and (".m3u8" in video_url or ".mp4" in video_url):
                    return {
                        "parse": 0,  # 0 代表已拿到直連，直接硬解播放
                        "playUrl": "",
                        "url": video_url,
                        "header": json.dumps(self.headers)
                    }
        except Exception:
            pass

        # 若未抓到直連，回退交給 OK影視 內建 WebView 嗅探網頁串流
        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page_url,
            "header": json.dumps(self.headers)
        }

    def _parse_vod_list(self, html, is_search=False):
        doc = pq(html)
        videos = []
        selector = ".module-search-item" if is_search else ".module-items .module-item"
        for item in doc(selector).items():
            a = item("a").eq(0)
            href = a.attr("href")
            title = a.attr("title") or item(".module-poster-item-title").text().strip()
            img = item("img").attr("data-original") or item("img").attr("src") or ""
            if img and not img.startswith("http"):
                img = self.host + img
            remark = item(".module-item-note").text().strip()

            if href and title:
                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": img,
                    "vod_remarks": remark
                })
        return videos

# coding=utf-8
import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "楓林網"

    def init(self, extend=""):
        self.host = "https://imaple.tv"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": f"{self.host}/"
        }

    def homeContent(self, filter):
        classes = [
            {"type_id": "2", "type_name": "電視劇"},
            {"type_id": "1", "type_name": "電影"},
            {"type_id": "4", "type_name": "動漫"},
            {"type_id": "3", "type_name": "綜藝"},
            {"type_id": "20", "type_name": "短劇"}
        ]
        return {"class": classes}

    def homeVideoContent(self):
        return self.categoryContent("2", "1", False, {})

    def categoryContent(self, tid, pg, filter, extend):
        # 支援標準 MacCMS 分類路徑 (/vodtype/{tid}-{pg}.html 或 /show/{tid}--------{pg}---.html)
        url = f"{self.host}/vodtype/{tid}-{pg}.html"
        res = requests.get(url, headers=self.headers, timeout=10)
        if res.status_code != 200:
            url = f"{self.host}/show/{tid}--------{pg}---.html"
            res = requests.get(url, headers=self.headers, timeout=10)

        soup = BeautifulSoup(res.text, "html.parser")
        videos = []

        # 解析常見海螺 / 蘋果CMS 影片卡片結構 (.module-item / .stui-vodlist__box / .myui-vodlist__box)
        items = soup.select(".module-item, .stui-vodlist__box, .myui-vodlist__box, li.hl-list-item")
        for item in items:
            a = item.find("a", href=re.compile(r"/(voddetail|detail|video)/"))
            if not a:
                a = item.find("a", href=True)
            if not a:
                continue

            href = a.get("href", "")
            full_url = href if href.startswith("http") else self.host + href
            title = a.get("title") or a.get_text(strip=True)
            if not title:
                continue

            img = item.find("img")
            pic = ""
            if img:
                pic = img.get("data-original") or img.get("data-src") or img.get("src") or ""
                if pic and not pic.startswith("http"):
                    pic = self.host + pic

            remark_el = item.select_one(".module-item-note, .pic-text, .hl-pic-text")
            remarks = remark_el.get_text(strip=True) if remark_el else ""

            if not any(v["vod_id"] == full_url for v in videos):
                videos.append({
                    "vod_id": full_url,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remarks
                })

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 99,
            "limit": 24,
            "total": 2000
        }

    def detailContent(self, ids):
        url = ids[0]
        res = requests.get(url, headers=self.headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        title_el = soup.find("h1")
        title = title_el.get_text(strip=True) if title_el else "未知影片"

        desc_el = soup.select_one(".module-info-introduction-content, .stui-content__desc, .hl-content-text")
        desc = desc_el.get_text(strip=True) if desc_el else ""

        img_el = soup.select_one(".module-item-pic img, .stui-content__thumb img, .hl-item-thumb")
        pic = ""
        if img_el:
            pic = img_el.get("data-original") or img_el.get("src") or ""
            if pic and not pic.startswith("http"):
                pic = self.host + pic

        # 提取播放線路名稱
        tabs = [t.get_text(strip=True) for t in soup.select(".module-tab-item span, .nav-tabs li a, .hl-tabs-btn")]
        # 提取對應的選集清單
        playlists = soup.select(".module-play-list-content, .stui-content__playlist, .hl-plays-list")

        play_from = []
        play_url = []

        for idx, pl in enumerate(playlists):
            line_name = tabs[idx] if idx < len(tabs) and tabs[idx] else f"線路{idx+1}"
            ep_list = []
            for a in pl.find_all("a", href=True):
                ep_name = a.get_text(strip=True)
                ep_href = a.get("href")
                if not ep_href.startswith("http"):
                    ep_href = self.host + ep_href
                ep_list.append(f"{ep_name}${ep_href}")
            if ep_list:
                play_from.append(line_name)
                play_url.append("#".join(ep_list))

        vod = {
            "vod_id": url,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "$$$".join(play_from) if play_from else "預設線路",
            "vod_play_url": "$$$".join(play_url) if play_url else f"正片${url}"
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        encoded_key = urllib.parse.quote(key)
        url = f"{self.host}/vodsearch/{encoded_key}----------{pg}---.html"
        res = requests.get(url, headers=self.headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        videos = []

        items = soup.select(".module-card-item, .stui-vodlist__media li, .hl-list-item")
        for item in items:
            a = item.find("a", href=re.compile(r"/(voddetail|detail|video)/"))
            if not a:
                continue
            href = a.get("href", "")
            full_url = href if href.startswith("http") else self.host + href
            title = a.get("title") or a.get_text(strip=True)
            img = item.find("img")
            pic = (img.get("data-original") or img.get("src") or "") if img else ""
            if pic and not pic.startswith("http"):
                pic = self.host + pic

            if title and not any(v["vod_id"] == full_url for v in videos):
                videos.append({
                    "vod_id": full_url,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": ""
                })
        return {"list": videos}

    def playerContent(self, flag, id, vipFlags):
        try:
            res = requests.get(id, headers=self.headers, timeout=10)
            # 1. 優先解析蘋果CMS player_aaaa JSON 內嵌串流
            player_match = re.search(r'var\s+player_aaaa\s*=\s*(\{.*?\});', res.text)
            if player_match:
                pdata = json.loads(player_match.group(1))
                v_url = pdata.get("url", "")
                if v_url and (".m3u8" in v_url or ".mp4" in v_url):
                    return {
                        "parse": 0,
                        "url": v_url,
                        "header": json.dumps(self.headers)
                    }

            # 2. 次之正則直接匹配 m3u8 / mp4
            m3u8_match = re.search(r'(https?://[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)', res.text)
            if m3u8_match:
                return {
                    "parse": 0,
                    "url": m3u8_match.group(1).replace("\\/", "/"),
                    "header": json.dumps(self.headers)
                }
        except Exception:
            pass

        # 3. 加密播放器回退至 TVBox 內建嗅探
        return {
            "parse": 1,
            "jx": 0,
            "url": id,
            "header": json.dumps(self.headers)
        }

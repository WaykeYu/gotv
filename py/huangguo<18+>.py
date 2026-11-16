# coding=utf-8
import re
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from base.spider import Spider

class Spider(Spider):
    def getName(self):
        return "黃果短劇"

    def init(self, extend=""):
        self.host = "https://huangguodrama.ai"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": f"{self.host}/zh-hant/library/"
        }

    def homeContent(self, filter):
        classes = [
            {"type_id": "all", "type_name": "全部作品"},
            {"type_id": "國產", "type_name": "國產"},
            {"type_id": "歐美", "type_name": "歐美"},
            {"type_id": "日本", "type_name": "日本"},
            {"type_id": "少婦熟女", "type_name": "少婦熟女"},
            {"type_id": "人妻", "type_name": "人妻"},
            {"type_id": "媽媽", "type_name": "媽媽"},
            {"type_id": "繼母", "type_name": "繼母"},
            {"type_id": "繼妹", "type_name": "繼妹"},
            {"type_id": "綠帽", "type_name": "綠帽"},
            {"type_id": "後宮", "type_name": "後宮"},
            {"type_id": "女同", "type_name": "女同"},
            {"type_id": "戶外露出", "type_name": "戶外露出"},
            {"type_id": "調教", "type_name": "調教"},
            {"type_id": "豪門", "type_name": "豪門"},
            {"type_id": "都市故事", "type_name": "都市故事"},
            {"type_id": "現代", "type_name": "現代"},
            {"type_id": "古風", "type_name": "古風"},
            {"type_id": "逆襲", "type_name": "逆襲"},
            {"type_id": "大男主", "type_name": "大男主"},
            {"type_id": "系統", "type_name": "系統"},
            {"type_id": "仙俠", "type_name": "仙俠"},
            {"type_id": "玄幻", "type_name": "玄幻"},
            {"type_id": "奇幻", "type_name": "奇幻"},
            {"type_id": "科幻", "type_name": "科幻"},
            {"type_id": "懸疑", "type_name": "懸疑"},
            {"type_id": "超能力", "type_name": "超能力"},
            {"type_id": "腦洞", "type_name": "腦洞"},
            {"type_id": "多角戀情", "type_name": "多角戀情"},
            {"type_id": "情感糾葛", "type_name": "情感糾葛"},
            {"type_id": "伴侶背叛", "type_name": "伴侶背叛"},
            {"type_id": "性轉", "type_name": "性轉"}
        ]
        return {"class": classes}

    def homeVideoContent(self):
        return self.categoryContent("all", "1", False, {})

    def _extract_cards(self, soup):
        videos = []
        seen_urls = set()

        # 尋找所有包含「集可觀看」或「開始觀看」的連結或父容器
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            # 排除導覽列、分頁、登入、標籤篩選連結
            if not href or href in ["/", "/zh-hant/", "/zh-hant/library/"]:
                continue
            if any(skip in href for skip in ["?page=", "?tag=", "/login", "/register", "/terms", "/privacy", "javascript:", "mailto:"]):
                continue
            if href.startswith("http") and not href.startswith(self.host):
                continue

            # 往上找最多 2 層父元素，涵蓋完整卡片文字與圖片
            card = a
            for _ in range(2):
                if card.parent and ("集可觀看" not in card.get_text() and card.parent.name in ["div", "article", "li"]):
                    card = card.parent

            card_text = card.get_text(" ", strip=True)
            if "集可觀看" not in card_text and "開始觀看" not in card_text:
                continue

            full_url = href if href.startswith("http") else self.host + href
            if full_url in seen_urls:
                continue

            # 提取劇名（優先找標題標籤或圖片 alt，避免抓到「開始觀看→」）
            title = ""
            for tag in card.find_all(["h2", "h3", "h4", "strong"]):
                t = tag.get_text(strip=True)
                if t and "集可觀看" not in t and "開始觀看" not in t and len(t) >= 2:
                    title = t
                    break
            if not title:
                img = card.find("img")
                if img and img.get("alt"):
                    title = img.get("alt").strip()
            if not title:
                raw_a = a.get_text(strip=True)
                if raw_a and "開始觀看" not in raw_a and "集可觀看" not in raw_a:
                    title = raw_a

            if not title or len(title) < 2:
                continue

            # 提取封面圖
            pic = ""
            img_el = card.find("img")
            if img_el:
                pic = img_el.get("src") or img_el.get("data-src") or ""
                if pic and not pic.startswith("http"):
                    pic = self.host + pic

            # 提取集數備註
            remarks = ""
            ep_match = re.search(r"(\d+\s*集可觀看)", card_text)
            if ep_match:
                remarks = ep_match.group(1)

            seen_urls.add(full_url)
            videos.append({
                "vod_id": full_url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks
            })

        return videos

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.host}/zh-hant/library/?page={pg}"
        if tid != "all":
            url += f"&tag={urllib.parse.quote(tid)}"
        
        res = requests.get(url, headers=self.headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        videos = self._extract_cards(soup)

        return {
            "list": videos,
            "page": int(pg),
            "pagecount": 22,
            "limit": 24,
            "total": 1085
        }

    def detailContent(self, ids):
        url = ids[0]
        res = requests.get(url, headers=self.headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")

        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "未知劇名"
        desc_el = soup.find("meta", {"name": "description"})
        desc = desc_el["content"] if desc_el else ""
        
        img_el = soup.find("meta", {"property": "og:image"})
        pic = img_el["content"] if img_el else ""

        play_list = []
        seen_eps = set()
        # 尋找詳情頁內所有集數按鈕或連結
        for a in soup.find_all("a", href=True):
            ep_href = a.get("href", "").strip()
            ep_text = a.get_text(strip=True)
            if re.search(r"(第\s*\d+\s*集|EP\s*\d+|^\d+$)", ep_text, re.I) or re.search(r"/(ep|episode|watch|play)/", ep_href):
                full_ep = ep_href if ep_href.startswith("http") else self.host + ep_href
                if full_ep not in seen_eps:
                    seen_eps.add(full_ep)
                    play_list.append(f"{ep_text or f'第{len(play_list)+1}集'}${full_ep}")

        if not play_list:
            play_list.append(f"立即觀看${url}")

        vod = {
            "vod_id": url,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "黃果短劇",
            "vod_play_url": "#".join(play_list)
        }
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/zh-hant/library/?q={urllib.parse.quote(key)}&page={pg}"
        res = requests.get(url, headers=self.headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        return {"list": self._extract_cards(soup)}

    def playerContent(self, flag, id, vipFlags):
        try:
            res = requests.get(id, headers=self.headers, timeout=10)
            m3u8_match = re.search(r'(https?://[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)', res.text)
            if m3u8_match:
                return {
                    "parse": 0,
                    "url": m3u8_match.group(1).replace("\\/", "/"),
                    "header": json.dumps(self.headers)
                }
        except Exception:
            pass

        return {
            "parse": 1,
            "jx": 0,
            "url": id,
            "header": json.dumps(self.headers)
        }

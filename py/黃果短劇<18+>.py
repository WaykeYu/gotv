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
            "Referer": f"{self.host}/zh-hant/library/",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8"
        }

    def homeContent(self, filter):
        # 1. 動態從片庫頁面抓取真實的英文路徑分類（如 /zh-hant/library/stepmom/），失敗則使用預設列表
        classes = [{"type_id": "all", "type_name": "全部作品"}]
        seen_ids = {"all"}

        try:
            res = requests.get(f"{self.host}/zh-hant/library/", headers=self.headers, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a.get("href", "").strip()
                m = re.match(r"^/zh-hant/(?:library|tag|category)/([a-zA-Z0-9_-]+)/?$", href)
                if m:
                    slug = m.group(1)
                    if slug.isdigit() or slug in ["novels", "comics", "games", "login"]:
                        continue
                    raw_name = a.get_text(strip=True)
                    clean_name = re.sub(r"\d+$", "", raw_name).strip()
                    if clean_name and slug not in seen_ids:
                        seen_ids.add(slug)
                        classes.append({"type_id": href, "type_name": clean_name})
        except Exception:
            pass

        if len(classes) <= 1:
            fallback = [
                ("/zh-hant/library/chinese/", "國產"),
                ("/zh-hant/library/western/", "歐美"),
                ("/zh-hant/library/japanese/", "日本"),
                ("/zh-hant/library/mature/", "少婦熟女"),
                ("/zh-hant/library/wife/", "人妻"),
                ("/zh-hant/library/mom/", "媽媽"),
                ("/zh-hant/library/stepmom/", "繼母"),
                ("/zh-hant/library/step-sis/", "繼妹"),
                ("/zh-hant/library/cuckold/", "綠帽"),
                ("/zh-hant/library/harem/", "後宮"),
                ("/zh-hant/library/lesbian/", "女同"),
                ("/zh-hant/library/public/", "戶外露出"),
                ("/zh-hant/library/bdsm/", "調教")
            ]
            for path, name in fallback:
                classes.append({"type_id": path, "type_name": name})

        # 2. 定義通用二級篩選條件（題材與標籤 + 中文字幕/配音過濾）
        genre_values = [
            {"n": "全部題材", "v": ""},
            {"n": "豪門", "v": "豪門"},
            {"n": "都市故事", "v": "都市故事"},
            {"n": "奇幻", "v": "奇幻"},
            {"n": "現代", "v": "現代"},
            {"n": "仙俠", "v": "仙俠"},
            {"n": "系統", "v": "系統"},
            {"n": "大男主", "v": "大男主"},
            {"n": "逆襲", "v": "逆襲"},
            {"n": "古風", "v": "古風"},
            {"n": "玄幻", "v": "玄幻"},
            {"n": "懸疑", "v": "懸疑"},
            {"n": "科幻", "v": "科幻"},
            {"n": "超能力", "v": "超能力"},
            {"n": "多角戀情", "v": "多角戀情"},
            {"n": "情感糾葛", "v": "情感糾葛"},
            {"n": "腦洞", "v": "腦洞"},
            {"n": "伴侶背叛", "v": "伴侶背叛"},
            {"n": "性轉", "v": "性轉"}
        ]

        lang_values = [
            {"n": "全部語言", "v": ""},
            {"n": "僅中文配音或中文字幕", "v": "1"}
        ]

        common_filters = [
            {"key": "tag", "name": "題材標籤", "value": genre_values},
            {"key": "zh", "name": "語言字幕", "value": lang_values}
        ]

        # 為每一個一級分類綁定這組二級篩選器
        filters = {c["type_id"]: common_filters for c in classes}

        return {
            "class": classes,
            "filters": filters
        }

    def homeVideoContent(self):
        return self.categoryContent("all", "1", False, {})

    def _parse_videos(self, html):
        videos = []
        seen_urls = set()
        soup = BeautifulSoup(html, "html.parser")

        # 1. 匹配純數字作品 ID 路徑（如 /zh-hant/library/169029/）
        for a in soup.find_all("a", href=re.compile(r"/zh-hant/(?:library/|drama/|watch/)?\d+/?$")):
            href = a.get("href", "").strip()
            full_url = href if href.startswith("http") else self.host + href
            if full_url in seen_urls:
                continue

            card = a
            for _ in range(3):
                if card.parent and card.parent.name in ["div", "article", "li"]:
                    txt = card.parent.get_text()
                    if "集可觀看" in txt or "開始觀看" in txt:
                        card = card.parent
                        break
                    card = card.parent

            title = ""
            for tag in card.find_all(["h2", "h3", "h4", "strong"]):
                t = tag.get_text(strip=True)
                if t and "集可觀看" not in t and "開始觀看" not in t and len(t) >= 2:
                    title = t
                    break
            if not title:
                t = a.get_text(strip=True)
                if t and "開始觀看" not in t and "集可觀看" not in t and len(t) >= 2:
                    title = t
            if not title:
                continue

            pic = ""
            img = card.find("img")
            if img:
                pic = img.get("src") or img.get("data-src") or ""
                if pic and not pic.startswith("http"):
                    pic = self.host + pic

            remarks = ""
            ep_match = re.search(r"(\d+\s*集可觀看)", card.get_text())
            if ep_match:
                remarks = ep_match.group(1)

            seen_urls.add(full_url)
            videos.append({
                "vod_id": full_url,
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks
            })

        # 2. 備援：從 Next.js __next_f 序列化資料提取純數字 ID 與標題
        if not videos:
            unescaped = html.replace('\\"', '"').replace('\\\\/', '/')
            for m in re.finditer(r'"id"\s*:\s*(\d{3,10})[^{}]{0,250}?"title"\s*:\s*"([^"\\]{2,60})"', unescaped):
                vid_num, title = m.group(1), m.group(2)
                full_url = f"{self.host}/zh-hant/library/{vid_num}/"
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    videos.append({
                        "vod_id": full_url,
                        "vod_name": title,
                        "vod_pic": "",
                        "vod_remarks": "短劇"
                    })

        return videos

    def categoryContent(self, tid, pg, filter, extend):
        if tid == "all":
            base_url = f"{self.host}/zh-hant/library/"
        else:
            base_url = tid if tid.startswith("http") else self.host + tid

        # 組合分頁與二級篩選查詢參數
        query_params = {}
        if str(pg) != "1":
            query_params["page"] = str(pg)

        tag_val = extend.get("tag", "")
        if tag_val:
            query_params["tag"] = tag_val

        zh_val = extend.get("zh", "")
        if zh_val:
            query_params["zh"] = zh_val

        url = base_url
        if query_params:
            sep = "&" if "?" in base_url else "?"
            url = f"{base_url}{sep}{urllib.parse.urlencode(query_params)}"

        res = requests.get(url, headers=self.headers, timeout=10)
        videos = self._parse_videos(res.text)

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

        vid_match = re.search(r"/(\d+)/?$", url)
        vid_num = vid_match.group(1) if vid_match else ""

        play_list = []
        seen_eps = set()
        for a in soup.find_all("a", href=True):
            ep_href = a.get("href", "").strip()
            ep_text = a.get_text(strip=True)
            is_ep_link = (vid_num and re.search(rf"/{vid_num}/(?:ep-?|episode-?|watch/)?\d+", ep_href)) or re.search(r"^(第\s*\d+\s*集|EP\s*\d+|\d+)$", ep_text, re.I)
            if is_ep_link:
                full_ep = ep_href if ep_href.startswith("http") else self.host + ep_href
                if full_ep not in seen_eps:
                    seen_eps.add(full_ep)
                    play_list.append(f"{ep_text or f'第{len(play_list)+1}集'}${full_ep}")

        if not play_list:
            play_list.append(f"立即觀看${url}")

        return {"list": [{
            "vod_id": url,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "黃果短劇",
            "vod_play_url": "#".join(play_list)
        }]}

    def searchContent(self, key, quick, pg="1"):
        url = f"{self.host}/zh-hant/library/?q={urllib.parse.quote(key)}&page={pg}"
        res = requests.get(url, headers=self.headers, timeout=10)
        return {"list": self._parse_videos(res.text)}

    def playerContent(self, flag, id, vipFlags):
        try:
            res = requests.get(id, headers=self.headers, timeout=10)
            m3u8_match = re.search(r'(https?://[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)', res.text)
            if m3u8_match:
                return {"parse": 0, "url": m3u8_match.group(1).replace("\\/", "/"), "header": json.dumps(self.headers)}
        except Exception:
            pass
        return {"parse": 1, "jx": 0, "url": id, "header": json.dumps(self.headers)}

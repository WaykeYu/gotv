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
            # 地區與特色分類 (13項)
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
            # 題材與標籤 (18項)
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

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.host}/zh-hant/library/?page={pg}"
        if tid != "all":
            url += f"&tag={urllib.parse.quote(tid)}"
        
        res = requests.get(url, headers=self.headers, timeout=10)
        soup = BeautifulSoup(res.text, "html.parser")
        videos = []

        # 解析片庫卡片列表
        for a in soup.find_all("a", href=re.compile(r"/zh-hant/(drama|watch|series)/")):
            href = a.get("href", "")
            if not href:
                continue
            full_url = href if href.startswith("http") else self.host + href
            
            title_el = a.find(["h2", "h3", "h4"])
            title = title_el.get_text(strip=True) if title_el else a.get_text(strip=True)
            if not title or len(title) < 2:
                continue

            img_el = a.find("img")
            pic = img_el.get("src", "") if img_el else ""
            if pic and not pic.startswith("http"):
                pic = self.host + pic

            remarks = ""
            ep_match = re.search(r"(\d+\s*集可觀看)", a.get_text())
            if ep_match:
                remarks = ep_match.group(1)

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
            "pagecount": 22,
            "limit": 24,
            "total": 1084
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
        ep_links = soup.find_all("a", href=re.compile(r"(ep|episode|watch|play)"))
        for idx, ep in enumerate(ep_links, 1):
            ep_url = ep.get("href")
            if not ep_url.startswith("http"):
                ep_url = self.host + ep_url
            ep_name = ep.get_text(strip=True) or f"第{idx}集"
            play_list.append(f"{ep_name}${ep_url}")

        if not play_list:
            play_list.append(f"第1集${url}")

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
        videos = []
        for a in soup.find_all("a", href=re.compile(r"/zh-hant/(drama|watch|series)/")):
            href = a.get("href", "")
            full_url = href if href.startswith("http") else self.host + href
            title_el = a.find(["h2", "h3", "h4"])
            title = title_el.get_text(strip=True) if title_el else ""
            if title and not any(v["vod_id"] == full_url for v in videos):
                img_el = a.find("img")
                pic = img_el.get("src", "") if img_el else ""
                videos.append({
                    "vod_id": full_url,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": "短劇"
                })
        return {"list": videos}

    def playerContent(self, flag, id, vipFlags):
        try:
            res = requests.get(id, headers=self.headers, timeout=10)
            m3u8_match = re.search(r'(https?://[^\s"\'<>]+\.(?:m3u8|mp4)[^\s"\'<>]*)', res.text)
            if m3u8_match:
                return {
                    "parse": 0,
                    "url": m3u8_match.group(1),
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

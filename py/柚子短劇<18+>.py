# -*- coding: utf-8 -*-
import html
import json
import re
import sys
import urllib.parse
import requests

sys.path.append('..')
from base.spider import Spider


class Spider(Spider):
    def getName(self):
        return "柚子短劇"

    def init(self, extend=""):
        self.host = "https://youzidj.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            "Referer": self.host + "/",
            "Origin": self.host
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self._verify_age()

    def _verify_age(self):
        """呼叫網站真實的 /api/age 接口取得伺服器簽發的年齡驗證 Cookie"""
        try:
            api_headers = {
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": self.host,
                "Referer": self.host + "/"
            }
            # 嘗試 POST 確認年齡（常見格式為空 JSON 或 confirmed: true）
            res = self.session.post(f"{self.host}/api/age", json={"confirmed": True}, headers=api_headers, timeout=8)
            if res.status_code not in (200, 204):
                self.session.get(f"{self.host}/api/age", headers=api_headers, timeout=8)
        except Exception:
            pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        classes = [
            {"type_name": "AI短劇", "type_id": "/dramas/"},
            {"type_name": "AI換臉", "type_id": "/ai-face-swap/"},
            {"type_name": "AI成人視頻", "type_id": "/ai-adult/"},
            {"type_name": "專題", "type_id": "/topics/"}
        ]
        result = {"class": classes, "list": []}
        try:
            res = self.session.get(self.host + "/dramas/", timeout=10)
            res.encoding = "utf-8"
            result["list"] = self._parse_cards(res.text)
        except Exception as e:
            result["list"] = [{"vod_id": "err", "vod_name": f"載入異常: {str(e)[:25]}", "vod_pic": "", "vod_remarks": ""}]
        return result

    def homeVideoContent(self):
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        result = {"page": int(pg), "pagecount": 99, "limit": 24, "total": 999, "list": []}
        try:
            base_url = f"{self.host}{tid}"
            url = base_url if int(pg) == 1 else f"{base_url}?page={pg}"
            res = self.session.get(url, timeout=10)
            res.encoding = "utf-8"
            videos = self._parse_cards(res.text)

            if not videos and int(pg) > 1:
                cat_slug = tid.strip("/")
                api_url = f"{self.host}/api/catalogue/browse?category={cat_slug}&page={pg}"
                api_res = self.session.get(api_url, timeout=10).json()
                videos = self._parse_api_items(api_res)

            result["list"] = videos
        except Exception:
            pass
        return result

    def detailContent(self, ids):
        vod_id = ids[0]
        if vod_id == "err":
            return {"list": []}
        url = vod_id if vod_id.startswith("http") else f"{self.host}{vod_id}"
        try:
            res = self.session.get(url, timeout=10)
            res.encoding = "utf-8"
            text = res.text

            title = ""
            pic = ""
            content = ""
            episodes = []

            ld_matches = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', text, re.S | re.I)
            for ld_raw in ld_matches:
                try:
                    data = json.loads(ld_raw.strip())
                    if data.get("@type") == "TVSeason":
                        title = data.get("name", "")
                        pic = data.get("image", "")
                        content = data.get("description", "")
                        for ep in data.get("episode", []):
                            ep_num = ep.get("episodeNumber", "")
                            ep_title = ep.get("name", "")
                            ep_url = ep.get("url", "")
                            if ep_url:
                                label = f"第{ep_num}集 {ep_title}".strip() if ep_num else ep_title
                                episodes.append(f"{label}${ep_url}")
                        break
                    elif data.get("@type") == "VideoObject" and not title:
                        title = data.get("name", "")
                        thumbs = data.get("thumbnailUrl", [])
                        pic = thumbs[0] if isinstance(thumbs, list) and thumbs else (thumbs if isinstance(thumbs, str) else "")
                        content = data.get("description", "")
                except Exception:
                    continue

            if not title:
                h1_m = re.search(r'<h1[^>]*>(.*?)</h1>', text, re.S | re.I)
                title = re.sub(r'<[^>]+>', '', h1_m.group(1)).strip() if h1_m else "未知影片"

            if not episodes:
                ep_links = re.findall(r'<a[^>]+class=["\'][^"\']*series-episode-link[^"\']*["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', text, re.S | re.I)
                if not ep_links:
                    ep_links = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*class=["\'][^"\']*series-episode-link[^"\']*["\'][^>]*>(.*?)</a>', text, re.S | re.I)
                for href, ep_num in ep_links:
                    ep_num_clean = re.sub(r'<[^>]+>', '', ep_num).strip()
                    episodes.append(f"第{ep_num_clean}集${href}")

            if not episodes:
                episodes.append(f"立即播放${url}")

            vod = {
                "vod_id": vod_id,
                "vod_name": html.unescape(title),
                "vod_pic": pic,
                "vod_content": html.unescape(content),
                "vod_play_from": "柚子直連$$$柚子嗅探",
                "vod_play_url": f"{'#'.join(episodes)}$$${'#'.join(episodes)}"
            }
            return {"list": [vod]}
        except Exception:
            return {"list": []}

    def searchContent(self, key, quick, pg="1"):
        try:
            encoded_key = urllib.parse.quote(key)
            api_url = f"{self.host}/api/catalogue/search?q={encoded_key}&page={pg}"
            res = self.session.get(api_url, timeout=10)
            if res.status_code == 200 and "application/json" in res.headers.get("Content-Type", ""):
                return {"list": self._parse_api_items(res.json())}

            page_url = f"{self.host}/search/?q={encoded_key}"
            page_res = self.session.get(page_url, timeout=10)
            page_res.encoding = "utf-8"
            return {"list": self._parse_cards(page_res.text)}
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        play_page_url = id if id.startswith("http") else f"{self.host}{id}"

        # 每次播放前確保已取得有效的年齡授權 Cookie
        if not self.session.cookies:
            self._verify_age()

        if flag == "柚子嗅探":
            return {
                "parse": 1,
                "playUrl": "",
                "url": play_page_url,
                "header": json.dumps({
                    "User-Agent": self.headers["User-Agent"],
                    "Referer": self.host + "/"
                })
            }

        try:
            res = self.session.get(play_page_url, timeout=10)
            res.encoding = "utf-8"
            text = res.text

            # 帶入由 /api/age 取得的所有 Session Cookies 與完整來源標頭
            play_headers = {
                "User-Agent": self.headers["User-Agent"],
                "Referer": play_page_url,
                "Origin": self.host
            }
            cookie_str = "; ".join([f"{k}={v}" for k, v in self.session.cookies.items()])
            if cookie_str:
                play_headers["Cookie"] = cookie_str

            ld_matches = re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', text, re.S | re.I)
            for ld_raw in ld_matches:
                try:
                    data = json.loads(ld_raw.strip())
                    if data.get("@type") == "VideoObject" and data.get("contentUrl"):
                        m3u8_url = html.unescape(data["contentUrl"].strip())
                        return {
                            "parse": 0,
                            "playUrl": "",
                            "url": m3u8_url,
                            "header": json.dumps(play_headers)
                        }
                except Exception:
                    continue

            vid_m = re.search(r'id=["\']player["\'][^>]*data-video=["\']([^"\']+)["\'][^>]*data-version=["\']([^"\']+)["\']', text, re.I)
            if vid_m:
                m3u8_url = f"{self.host}/media/{vid_m.group(1)}/{vid_m.group(2)}/master.m3u8"
                return {
                    "parse": 0,
                    "playUrl": "",
                    "url": m3u8_url,
                    "header": json.dumps(play_headers)
                }
        except Exception:
            pass

        return {
            "parse": 1,
            "playUrl": "",
            "url": play_page_url,
            "header": json.dumps(self.headers)
        }

    def _parse_cards(self, html_text):
        videos = []
        seen = set()
        articles = re.findall(r'<article[^>]*class=["\'][^"\']*drama-card[^"\']*["\'][^>]*>(.*?)</article>', html_text, re.S | re.I)
        for art in articles:
            href_m = re.search(r'<a[^>]+href=["\']([^"\']+)["\']', art, re.I)
            if not href_m:
                continue
            href = href_m.group(1)
            if href in seen:
                continue

            title_m = re.search(r'class=["\'][^"\']*drama-card-title[^"\']*["\'][^>]*title=["\']([^"\']+)["\']', art, re.I)
            if not title_m:
                title_m = re.search(r'aria-label=["\']查看详情：([^"\']+)["\']', art, re.I)
            title = html.unescape(title_m.group(1).strip()) if title_m else ""

            img_m = re.search(r'<img[^>]+src=["\']([^"\']+/catalogue-art/[^"\']+)["\']', art, re.I)
            pic = img_m.group(1) if img_m else ""
            if pic and not pic.startswith("http"):
                pic = self.host + (pic if pic.startswith("/") else "/" + pic)

            ep_m = re.search(r'class=["\'][^"\']*home-card-episodes-long[^"\']*["\'][^>]*>(.*?)</span>', art, re.S | re.I)
            remark = re.sub(r'<[^>]+>', '', ep_m.group(1)).strip() if ep_m else ""

            if href and title:
                seen.add(href)
                videos.append({
                    "vod_id": href,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
        return videos

    def _parse_api_items(self, data):
        videos = []
        items = data if isinstance(data, list) else data.get("items") or data.get("data") or data.get("results") or []
        for item in items:
            slug = item.get("slug") or item.get("url") or item.get("path") or ""
            if slug and not slug.startswith("/") and not slug.startswith("http"):
                slug = f"/dramas/{slug}/season-1/"
            title = item.get("title") or item.get("name") or ""
            pic = item.get("cover") or item.get("image") or item.get("poster") or ""
            if pic and not pic.startswith("http"):
                pic = self.host + (pic if pic.startswith("/") else "/" + pic)
            ep_count = item.get("episodeCount") or item.get("episodes") or ""
            remark = f"更新至{ep_count}集" if ep_count else ""
            if slug and title:
                videos.append({
                    "vod_id": slug,
                    "vod_name": title,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
        return videos

# coding=utf-8
import re
import json
import urllib.parse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from base.spider import Spider


class Spider(Spider):
    # 預先編譯正則表達式
    RE_CLASS_HREF = re.compile(r"^/zh-hant/(?:library|tag|category)/([a-zA-Z0-9_-]+)/?$")
    RE_TRAILING_NUM = re.compile(r"\d+$")
    RE_VOD_HREF = re.compile(r"(?:^|/)\d{3,10}(?:/|$|\?)")
    RE_VID_NUM = re.compile(r"\d{3,10}")
    RE_EP_REMARKS = re.compile(r"(\d+\s*集可觀看)")
    RE_JSON_VOD = re.compile(r'"id"\s*:\s*"?(\d{3,10})"?[^{}]{0,300}?"title"\s*:\s*"([^"\\]{2,60})"')
    RE_EP_TEXT = re.compile(r"^(?:第\s*\d+\s*[集話期]|EP\s*\d+|\d+)$", re.I)
    RE_VIDEO_URL = re.compile(r'(https?:\\?/\\?/[^\s"\'<>\\]+\.(?:m3u8|mp4)[^\s"\'<>\\]*)')
    RE_PAGE_NUM = re.compile(r"[?&]page=(\d+)")

    EXCLUDE_SLUGS = {"novels", "comics", "games", "login"}
    EXCLUDE_HREF_KEYS = ("page=", "login", "register", "novels", "comics")
    EXCLUDE_LINE_KEYS = ("集可觀看", "開始觀看", "分", "國產", "歐美", "日本")

    FALLBACK_CLASSES = [
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
        ("/zh-hant/library/bdsm/", "調教"),
    ]

    GENRE_LIST = [
        "豪門", "都市故事", "奇幻", "現代", "仙俠", "系統", "大男主", "逆襲",
        "古風", "玄幻", "懸疑", "科幻", "超能力", "多角戀情", "情感糾葛",
        "腦洞", "伴侶背叛", "性轉"
    ]

    def getName(self):
        return "黃果短劇"

    def init(self, extend=""):
        self.host = "https://huangguodrama.ai"
        self.base_lib = f"{self.host}/zh-hant/library/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            "Referer": self.base_lib,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        }

        self.session = requests.Session()
        self.session.headers.update(self.headers)
        retries = Retry(total=2, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retries, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def _fetch(self, url, timeout=10):
        return self.session.get(url, timeout=timeout)

    def _normalize_url(self, href):
        if not href:
            return ""
        return urllib.parse.urljoin(self.base_lib, href.strip())

    def homeContent(self, filter):
        classes = [{"type_id": "all", "type_name": "全部作品"}]
        seen_ids = {"all"}

        try:
            res = self._fetch(self.base_lib)
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                m = self.RE_CLASS_HREF.match(href)
                if not m:
                    continue
                slug = m.group(1)
                if slug.isdigit() or slug in self.EXCLUDE_SLUGS or slug in seen_ids:
                    continue
                clean_name = self.RE_TRAILING_NUM.sub("", a.get_text(strip=True)).strip()
                if clean_name:
                    seen_ids.add(slug)
                    classes.append({"type_id": href, "type_name": clean_name})
        except Exception:
            pass

        if len(classes) <= 1:
            classes.extend({"type_id": path, "type_name": name} for path, name in self.FALLBACK_CLASSES)

        genre_values = [{"n": "全部題材", "v": ""}] + [{"n": g, "v": g} for g in self.GENRE_LIST]
        lang_values = [
            {"n": "全部語言", "v": ""},
            {"n": "僅中文配音或中文字幕", "v": "1"},
        ]

        common_filters = [
            {"key": "tag", "name": "題材標籤", "value": genre_values},
            {"key": "zh", "name": "語言字幕", "value": lang_values},
        ]

        return {
            "class": classes,
            "filters": {c["type_id"]: common_filters for c in classes},
        }

    def homeVideoContent(self):
        return self.categoryContent("all", "1", False, {})

    def _extract_pagecount(self, soup, current_pg):
        max_pg = int(current_pg)
        for a in soup.find_all("a", href=True):
            m = self.RE_PAGE_NUM.search(a["href"])
            if m:
                max_pg = max(max_pg, int(m.group(1)))
        return max_pg

    def _parse_videos(self, html, status_code=200, current_pg=1):
        videos = []
        seen_vids = set()
        seen_titles = set()
        soup = BeautifulSoup(html, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            vid_match = self.RE_VOD_HREF.search(href)
            if not vid_match:
                continue
            if any(x in href for x in self.EXCLUDE_HREF_KEYS):
                continue

            vid_num = self.RE_VID_NUM.search(vid_match.group(0)).group(0)
            if vid_num in seen_vids:
                continue

            # 保留原始真實路徑（去除多餘的 query 參數即可，不再硬改目錄名稱）
            raw_full_url = self._normalize_url(href)
            clean_url = raw_full_url.split("?")[0]

            # 向上尋找單張卡片容器
            card = a
            curr = a.parent
            for _ in range(6):
                if not curr or curr.name not in ("div", "article", "li", "section"):
                    break
                txt = curr.get_text(" ", strip=True)
                if txt.count("開始觀看") > 1 or txt.count("集可觀看") > 1:
                    break
                card = curr
                if "集可觀看" in txt:
                    break
                curr = curr.parent

            # 1. 提取標題
            title = ""
            for tag in card.find_all(["h1", "h2", "h3", "h4", "strong"]):
                t = tag.get_text(strip=True)
                if len(t) >= 2 and "集可觀看" not in t and "開始觀看" not in t:
                    title = t
                    break

            img_el = card.find("img")
            if not title and img_el and img_el.get("alt"):
                alt_t = img_el["alt"].strip()
                if len(alt_t) >= 2 and "logo" not in alt_t.lower():
                    title = alt_t

            card_lines = card.get_text("\n", strip=True)
            if not title:
                for line in card_lines.split("\n"):
                    line = line.strip()
                    if len(line) >= 2 and not any(k in line for k in self.EXCLUDE_LINE_KEYS):
                        title = line
                        break

            if not title or title in seen_titles:
                continue

            # 2. 提取封面圖
            pic = ""
            if img_el:
                raw_pic = img_el.get("src") or img_el.get("data-src") or img_el.get("srcset", "").split(" ")[0]
                pic = self._normalize_url(raw_pic)

            # 3. 提取集數備註
            ep_match = self.RE_EP_REMARKS.search(card_lines)
            remarks = ep_match.group(1) if ep_match else ""

            seen_vids.add(vid_num)
            seen_titles.add(title)
            videos.append({
                "vod_id": clean_url,  # 直接使用網頁上原本的有效連結
                "vod_name": title,
                "vod_pic": pic,
                "vod_remarks": remarks,
            })

        # Fallback: 嘗試從內嵌 JSON 撈取
        if not videos:
            unescaped = html.replace('\\"', '"').replace("\\\\/", "/")
            for m in self.RE_JSON_VOD.finditer(unescaped):
                vid_num, title = m.group(1), m.group(2)
                if vid_num not in seen_vids and title not in seen_titles and not any(k in title for k in ("黃果", "片庫", "首頁")):
                    seen_vids.add(vid_num)
                    seen_titles.add(title)
                    videos.append({
                        "vod_id": f"{self.host}/zh-hant/drama/{vid_num}/",
                        "vod_name": title,
                        "vod_pic": "",
                        "vod_remarks": "短劇",
                    })

        if not videos:
            sample_hrefs = [
                a["href"] for a in soup.find_all("a", href=True)
                if any(c.isdigit() for c in a["href"])
            ][:3]
            videos.append({
                "vod_id": self.base_lib,
                "vod_name": f"[診斷] HTTP:{status_code} | 樣本:{','.join(sample_hrefs) or '無數字連結'}",
                "vod_pic": "",
                "vod_remarks": f"HTML長度:{len(html)}",
            })

        pagecount = self._extract_pagecount(soup, current_pg)
        return videos, pagecount

    def categoryContent(self, tid, pg, filter, extend):
        base_url = self.base_lib if tid == "all" else self._normalize_url(tid)
        pg_int = int(pg)

        query_params = {}
        if pg_int > 1:
            query_params["page"] = str(pg_int)
        if extend.get("tag"):
            query_params["tag"] = extend["tag"]
        if extend.get("zh"):
            query_params["zh"] = extend["zh"]

        url = base_url
        if query_params:
            sep = "&" if "?" in base_url else "?"
            url = f"{base_url}{sep}{urllib.parse.urlencode(query_params)}"

        try:
            res = self._fetch(url)
            videos, pagecount = self._parse_videos(res.text, res.status_code, pg_int)
        except Exception as e:
            pagecount = pg_int
            videos = [{
                "vod_id": url,
                "vod_name": f"[連線異常] {str(e)[:40]}",
                "vod_pic": "",
                "vod_remarks": "請求失敗",
            }]

        return {
            "list": videos,
            "page": pg_int,
            "pagecount": pagecount,
            "limit": len(videos) or 24,
            "total": pagecount * 24,
        }

    def detailContent(self, ids):
        url = ids[0]
        try:
            res = self._fetch(url)
            html = res.text
            soup = BeautifulSoup(html, "html.parser")
        except Exception as e:
            return {"list": [{
                "vod_id": url,
                "vod_name": "載入失敗",
                "vod_content": str(e),
                "vod_play_from": "黃果短劇",
                "vod_play_url": f"重試${url}",
            }]}

        h1 = soup.find("h1")
        title = h1.get_text(strip=True) if h1 else ""
        if not title or title == "404":
            og_title = soup.find("meta", {"property": "og:title"})
            title = og_title.get("content", "未知劇名").split("-")[0].strip() if og_title else "未知劇名"

        desc_el = soup.find("meta", {"name": "description"})
        desc = desc_el.get("content", "") if desc_el else ""
        img_el = soup.find("meta", {"property": "og:image"})
        pic = self._normalize_url(img_el.get("content", "")) if img_el else ""

        vid_match = self.RE_VID_NUM.search(url)
        vid_num = vid_match.group(0) if vid_match else ""
        ep_href_re = re.compile(rf"/{vid_num}/(?:ep-?|episode-?|watch/|play/)?\d+") if vid_num else None

        play_list = []
        seen_eps = set()

        # 1. 從網頁 <a> 標籤提取分集連結
        for a in soup.find_all("a", href=True):
            ep_href = a["href"].strip()
            ep_text = a.get_text(strip=True)
            is_ep_link = (ep_href_re and ep_href_re.search(ep_href)) or self.RE_EP_TEXT.search(ep_text)
            if is_ep_link:
                full_ep = self._normalize_url(ep_href)
                if full_ep not in seen_eps and full_ep != url:
                    seen_eps.add(full_ep)
                    play_list.append(f"{ep_text or f'第{len(play_list) + 1}集'}${full_ep}")

        # 2. 若 <a> 標籤沒抓到（例如單頁動態切換集數），嘗試從網頁文字或 JSON 偵測總集數並構造連結
        if not play_list and vid_num:
            unescaped = html.replace('\\"', '"').replace("\\\\/", "/")
            # 尋找內嵌的 m3u8 / mp4 清單
            direct_streams = self.RE_VIDEO_URL.findall(unescaped)
            for idx, stream in enumerate(dict.fromkeys(direct_streams), 1):
                clean_stream = stream.replace("\\/", "/")
                play_list.append(f"第{idx}集${clean_stream}")

        if not play_list:
            play_list.append(f"立即觀看${url}")

        return {"list": [{
            "vod_id": url,
            "vod_name": title,
            "vod_pic": pic,
            "vod_content": desc,
            "vod_play_from": "黃果短劇",
            "vod_play_url": "#".join(play_list),
        }]}

    def searchContent(self, key, quick, pg="1"):
        pg_int = int(pg)
        url = f"{self.base_lib}?q={urllib.parse.quote(key)}&page={pg_int}"
        try:
            res = self._fetch(url)
            videos, pagecount = self._parse_videos(res.text, res.status_code, pg_int)
            return {
                "list": videos,
                "page": pg_int,
                "pagecount": pagecount,
                "limit": len(videos) or 24,
                "total": pagecount * 24,
            }
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        # 若在 detailContent 已直接提取出 m3u8 / mp4 直鏈，直接交給播放器
        if re.search(r"\.(?:m3u8|mp4)(?:\?|$)", id, re.I):
            return {
                "parse": 0,
                "url": id,
                "header": json.dumps(self.headers),
            }

        try:
            res = self._fetch(id)
            unescaped = res.text.replace("\\/", "/")
            m3u8_match = self.RE_VIDEO_URL.search(unescaped)
            if m3u8_match:
                return {
                    "parse": 0,
                    "url": m3u8_match.group(1),
                    "header": json.dumps(self.headers),
                }
        except Exception:
            pass

        # 若無靜態直鏈，交由 TVBox WebView 嗅探播放
        return {
            "parse": 1,
            "jx": 0,
            "url": id,
            "header": json.dumps(self.headers),
        }

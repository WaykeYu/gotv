# coding=utf-8
#!/usr/bin/python
import sys
import json
import re
import urllib.parse
import requests
from base.spider import Spider

sys.path.append('..')


class Spider(Spider):
    def getName(self):
        return "洛雪TV"

    def init(self, extend=""):
        self.host = "https://tv.lxyy.club"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Referer": f"{self.host}/",
            "Origin": self.host,
            "Accept": "application/json, text/plain, */*"
        }
        # 預設常見的采集站/後端聚合接口與TMDB備援配置（可透過 extend 傳入自訂 JSON 覆蓋）
        self.config = {
            "api_base": f"{self.host}/api",
            "tmdb_api": "https://api.themoviedb.org/3",
            "tmdb_img": "https://image.tmdb.org/t/p/w500",
            "tmdb_key": ""  # 若網站後端API變動，可在 TVBox ext 中填入 {"tmdb_key": "你的KEY"}
        }
        if extend:
            try:
                ext_data = json.loads(extend) if isinstance(extend, str) else extend
                self.config.update(ext_data)
            except Exception:
                pass

    def isVideoFormat(self, url):
        return bool(re.search(r'\.(m3u8|mp4|mkv|flv|mpd)(\?.*)?$', url, re.I))

    def manualVideoCheck(self):
        return False

    def homeContent(self, filter):
        result = {}
        # 1. 完整分類（對應洛雪TV導航欄與夸克榜單頻道）
        classes = [
            {"type_name": "推荐榜单", "type_id": "recommend"},
            {"type_name": "电影", "type_id": "movie"},
            {"type_name": "剧集", "type_id": "tv"},
            {"type_name": "动漫", "type_id": "anime"},
            {"type_name": "综艺", "type_id": "variety"},
            {"type_name": "短剧", "type_id": "short"},
            {"type_name": "最近更新", "type_id": "recent"}
        ]
        result['class'] = classes

        # 2. 完整篩選條件（類型、地區、年份、排序/榜單來源）
        if filter:
            genres_movie = [
                {"n": "全部", "v": ""}, {"n": "动作", "v": "28"}, {"n": "冒险", "v": "12"},
                {"n": "动画", "v": "16"}, {"n": "喜剧", "v": "35"}, {"n": "犯罪", "v": "80"},
                {"n": "纪录", "v": "99"}, {"n": "剧情", "v": "18"}, {"n": "家庭", "v": "10751"},
                {"n": "奇幻", "v": "14"}, {"n": "历史", "v": "36"}, {"n": "恐怖", "v": "27"},
                {"n": "悬疑", "v": "9648"}, {"n": "爱情", "v": "10749"}, {"n": "科幻", "v": "878"},
                {"n": "惊悚", "v": "53"}, {"n": "战争", "v": "10752"}
            ]
            genres_tv = [
                {"n": "全部", "v": ""}, {"n": "动作冒险", "v": "10759"}, {"n": "动画", "v": "16"},
                {"n": "喜剧", "v": "35"}, {"n": "犯罪", "v": "80"}, {"n": "纪录", "v": "99"},
                {"n": "剧情", "v": "18"}, {"n": "家庭", "v": "10751"}, {"n": "儿童", "v": "10762"},
                {"n": "悬疑", "v": "9648"}, {"n": "真人秀", "v": "10764"}, {"n": "科幻奇幻", "v": "10765"},
                {"n": "战争政治", "v": "10768"}
            ]
            areas = [
                {"n": "全部", "v": ""}, {"n": "中国大陆", "v": "CN"}, {"n": "中国香港", "v": "HK"},
                {"n": "中国台湾", "v": "TW"}, {"n": "美国", "v": "US"}, {"n": "韩国", "v": "KR"},
                {"n": "日本", "v": "JP"}, {"n": "英国", "v": "GB"}, {"n": "泰国", "v": "TH"},
                {"n": "其他", "v": "OTHER"}
            ]
            years = [{"n": "全部", "v": ""}] + [
                {"n": str(y), "v": str(y)} for y in range(2026, 2009, -1)
            ] + [{"n": "更早", "v": "before_2010"}]

            sorts = [
                {"n": "综合热度", "v": "popularity.desc"},
                {"n": "最新上线", "v": "release_date.desc"},
                {"n": "高分好评", "v": "vote_average.desc"},
                {"n": "夸克热搜", "v": "quark"},
                {"n": "TMDB趋势", "v": "tmdb_trending"}
            ]

            recommend_sources = [
                {"n": "全部榜单", "v": "all"},
                {"n": "Nostr社区热度", "v": "nostr"},
                {"n": "TMDB每日趋势", "v": "tmdb"},
                {"n": "夸克影视热搜", "v": "quark"}
            ]

            filters = {
                "recommend": [
                    {"key": "source", "name": "榜单来源", "value": recommend_sources},
                    {"key": "channel", "name": "频道", "value": [
                        {"n": "全部", "v": ""}, {"n": "电视剧", "v": "tv"},
                        {"n": "电影", "v": "movie"}, {"n": "综艺", "v": "variety"},
                        {"n": "动漫", "v": "anime"}, {"n": "短剧", "v": "short"}
                    ]}
                ],
                "movie": [
                    {"key": "class", "name": "类型", "value": genres_movie},
                    {"key": "area", "name": "地区", "value": areas},
                    {"key": "year", "name": "年份", "value": years},
                    {"key": "sort", "name": "排序", "value": sorts}
                ],
                "tv": [
                    {"key": "class", "name": "类型", "value": genres_tv},
                    {"key": "area", "name": "地区", "value": areas},
                    {"key": "year", "name": "年份", "value": years},
                    {"key": "sort", "name": "排序", "value": sorts}
                ],
                "anime": [
                    {"key": "area", "name": "地区", "value": [
                        {"n": "全部", "v": ""}, {"n": "日本", "v": "JP"},
                        {"n": "中国大陆", "v": "CN"}, {"n": "欧美", "v": "US"}
                    ]},
                    {"key": "year", "name": "年份", "value": years},
                    {"key": "sort", "name": "排序", "value": sorts}
                ],
                "variety": [
                    {"key": "area", "name": "地区", "value": areas},
                    {"key": "year", "name": "年份", "value": years},
                    {"key": "sort", "name": "排序", "value": sorts}
                ],
                "short": [
                    {"key": "class", "name": "题材", "value": [
                        {"n": "全部", "v": ""}, {"n": "都市", "v": "都市"},
                        {"n": "古装", "v": "古装"}, {"n": "逆袭", "v": "逆袭"},
                        {"n": "甜宠", "v": "甜宠"}, {"n": "悬疑", "v": "悬疑"}
                    ]},
                    {"key": "sort", "name": "排序", "value": sorts}
                ],
                "recent": [
                    {"key": "channel", "name": "类型", "value": [
                        {"n": "全部", "v": ""}, {"n": "电影", "v": "movie"},
                        {"n": "剧集", "v": "tv"}, {"n": "动漫", "v": "anime"}
                    ]}
                ]
            }
            result['filters'] = filters

        return result

    def homeVideoContent(self):
        # 首頁推薦內容
        data = self.categoryContent("recommend", "1", False, {"source": "all"})
        return {"list": data.get("list", [])[:18]}

    def categoryContent(self, tid, pg, filter, extend):
        page = int(pg)
        videos = []
        total_pages = 56

        # 組合查詢參數，向洛雪TV後端 / 聚合介面請求
        params = {
            "type": tid,
            "page": page,
            "limit": 18,
            "class": extend.get("class", ""),
            "area": extend.get("area", ""),
            "year": extend.get("year", ""),
            "sort": extend.get("sort", "popularity.desc"),
            "source": extend.get("source", ""),
            "channel": extend.get("channel", "")
        }

        # 嘗試從洛雪TV網站 API 獲取數據
        api_endpoints = [
            f"{self.host}/api/vod/list",
            f"{self.host}/api/discover",
            f"{self.host}/api/tmdb/discover"
        ]

        fetched = False
        for endpoint in api_endpoints:
            try:
                resp = requests.get(endpoint, params=params, headers=self.headers, timeout=8)
                if resp.status_code == 200 and resp.text.strip().startswith("{"):
                    data = resp.json()
                    items = data.get("list") or data.get("results") or data.get("data", [])
                    if items:
                        total_pages = data.get("pagecount") or data.get("total_pages") or 56
                        for item in items:
                            videos.append(self._format_vod_item(item, tid))
                        fetched = True
                        break
            except Exception:
                continue

        # 若直接 API 路徑變更，透過網站前端配置提取 TMDB Key 或采集站列表作為備援
        if not fetched:
            videos = self._fallback_discover(tid, page, extend)

        return {
            "list": videos,
            "page": page,
            "pagecount": total_pages,
            "limit": 18,
            "total": total_pages * 18
        }

    def detailContent(self, ids):
        vod_id = str(ids[0])
        # vod_id 格式範例: "movie_12345_片名" 或 "tv_12345_片名" 或采集站ID
        parts = vod_id.split("_", 2)
        media_type = parts[0] if len(parts) > 1 else "movie"
        raw_id = parts[1] if len(parts) > 1 else vod_id
        title = parts[2] if len(parts) > 2 else ""

        vod = {
            "vod_id": vod_id,
            "vod_name": title or f"影视详情 ({raw_id})",
            "vod_pic": "",
            "type_name": media_type,
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": "",
            "vod_actor": "",
            "vod_director": "",
            "vod_content": ""
        }

        play_from = []
        play_url = []

        # 1. 嘗試獲取洛雪TV詳情與多線路播放列表（官采線路、4K60幀、自營采集線路）
        try:
            detail_url = f"{self.host}/api/vod/detail"
            resp = requests.get(
                detail_url,
                params={"id": raw_id, "type": media_type, "wd": title},
                headers=self.headers,
                timeout=8
            )
            if resp.status_code == 200 and resp.text.strip().startswith("{"):
                data = resp.json()
                info = data.get("data") or data
                vod["vod_name"] = info.get("vod_name") or info.get("title") or info.get("name") or vod["vod_name"]
                vod["vod_pic"] = self._fix_img(info.get("vod_pic") or info.get("poster_path", ""))
                vod["vod_year"] = str(info.get("vod_year") or info.get("release_date", "")[:4])
                vod["vod_area"] = info.get("vod_area", "")
                vod["vod_actor"] = info.get("vod_actor", "")
                vod["vod_director"] = info.get("vod_director", "")
                vod["vod_content"] = info.get("vod_content") or info.get("overview", "")

                # 解析多線路播放源
                sources = info.get("sources") or info.get("play_list") or []
                if isinstance(sources, list) and sources:
                    for src in sources:
                        src_name = src.get("name") or src.get("from") or "默认线路"
                        episodes = src.get("episodes") or src.get("urls") or []
                        ep_list = []
                        for ep in episodes:
                            ep_name = ep.get("name") or ep.get("title") or "正片"
                            ep_link = ep.get("url") or ep.get("link") or ""
                            if ep_link:
                                ep_list.append(f"{ep_name}${ep_link}")
                        if ep_list:
                            play_from.append(src_name)
                            play_url.append("#".join(ep_list))
                elif info.get("vod_play_from") and info.get("vod_play_url"):
                    vod["vod_play_from"] = info["vod_play_from"]
                    vod["vod_play_url"] = info["vod_play_url"]
                    return {"list": [vod]}
        except Exception:
            pass

        # 2. 若網站 API 未直接返回線路，自動透過片名搜尋洛雪TV內建采集源介面
        if not play_from and vod["vod_name"]:
            search_sources = self._search_collect_sources(vod["vod_name"])
            for s_name, s_urls in search_sources:
                play_from.append(s_name)
                play_url.append(s_urls)

        vod["vod_play_from"] = "$$$".join(play_from) if play_from else "洛雪4K解析"
        vod["vod_play_url"] = "$$$".join(play_url) if play_url else f"暂无可用线路${self.host}"

        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        page = int(pg)
        videos = []

        # 1. 請求洛雪TV 站內搜索（含 TMDB 庫與采集站聚合搜索）
        search_endpoints = [
            f"{self.host}/api/vod/search",
            f"{self.host}/api/search",
            f"{self.host}/api/collect/search"
        ]
        for ep in search_endpoints:
            try:
                resp = requests.get(
                    ep,
                    params={"wd": key, "q": key, "query": key, "page": page},
                    headers=self.headers,
                    timeout=8
                )
                if resp.status_code == 200 and resp.text.strip().startswith("{"):
                    data = resp.json()
                    items = data.get("list") or data.get("results") or data.get("data", [])
                    for item in items:
                        videos.append(self._format_vod_item(item, "search"))
                    if videos:
                        break
            except Exception:
                continue

        return {
            "list": videos,
            "page": page,
            "pagecount": 10 if videos else 1,
            "limit": 18,
            "total": len(videos)
        }

    def playerContent(self, flag, id, vipFlags):
        """
        處理播放連結：
        1. 若為 m3u8 / mp4 等直鏈，直接返回播放。
        2. 若為騰訊、愛奇藝、優酷、芒果、B站等官采平台頁面連結，自動交由洛雪4K / 預設解析介面或 TVBox 嗅探播放。
        """
        url = id.strip()
        if self.isVideoFormat(url):
            return {
                "parse": 0,
                "playUrl": "",
                "url": url,
                "header": json.dumps({"User-Agent": self.headers["User-Agent"]})
            }

        # 檢查是否為官采平台連結（v.qq.com, iqiyi.com, youku.com, mgtv.com, bilibili.com）
        official_domains = ["v.qq.com", "iqiyi.com", "youku.com", "mgtv.com", "bilibili.com"]
        is_official = any(domain in url for domain in official_domains)

        if is_official:
            # 優先呼叫洛雪TV後端解析介面（對應說明中的「默认解析 / 洛雪4K」）
            try:
                parse_api = f"{self.host}/api/parse"
                resp = requests.get(
                    parse_api,
                    params={"url": url, "line": flag},
                    headers=self.headers,
                    timeout=8
                )
                if resp.status_code == 200 and resp.text.strip().startswith("{"):
                    pdata = resp.json()
                    real_url = pdata.get("url") or pdata.get("data", {}).get("url", "")
                    if real_url and self.isVideoFormat(real_url):
                        return {
                            "parse": 0,
                            "playUrl": "",
                            "url": real_url,
                            "header": json.dumps({"User-Agent": self.headers["User-Agent"]})
                        }
            except Exception:
                pass

            # 若後端未直接吐出直鏈，交給 TVBox 內建解析器 / WebView 嗅探
            return {
                "parse": 1,
                "jx": 1,
                "playUrl": "",
                "url": url,
                "header": json.dumps({"User-Agent": self.headers["User-Agent"]})
            }

        # 其他情況開啟 WebView 嗅探模式
        return {
            "parse": 1,
            "playUrl": "",
            "url": url,
            "header": json.dumps({"User-Agent": self.headers["User-Agent"]})
        }

    # ================= 內部輔助方法 =================

    def _format_vod_item(self, item, default_type="movie"):
        raw_id = str(item.get("vod_id") or item.get("id") or "")
        title = item.get("vod_name") or item.get("title") or item.get("name") or "未知影片"
        m_type = item.get("media_type") or ("tv" if default_type in ["tv", "anime", "variety", "short"] else "movie")
        pic = self._fix_img(item.get("vod_pic") or item.get("poster_path") or item.get("pic") or "")
        remarks = item.get("vod_remarks") or item.get("remarks") or ""
        if not remarks and item.get("vote_average"):
            remarks = f"评分 {round(float(item['vote_average']), 1)}"
        elif not remarks and item.get("heat"):
            remarks = f"{item['heat']}人观看"

        return {
            "vod_id": f"{m_type}_{raw_id}_{title}",
            "vod_name": title,
            "vod_pic": pic,
            "vod_remarks": str(remarks)
        }

    def _fix_img(self, path):
        if not path:
            return ""
        if path.startswith("http"):
            return path
        if path.startswith("/"):
            return f"{self.config['tmdb_img']}{path}"
        return path

    def _search_collect_sources(self, keyword):
        """模擬洛雪TV詳情頁的「搜索采集源」功能，聚合多個采集線路"""
        results = []
        try:
            resp = requests.get(
                f"{self.host}/api/collect/search",
                params={"wd": keyword},
                headers=self.headers,
                timeout=8
            )
            if resp.status_code == 200 and resp.text.strip().startswith("{"):
                data = resp.json()
                sources = data.get("list") or data.get("data") or []
                for idx, s in enumerate(sources):
                    site_name = s.get("site_name") or s.get("vod_play_from") or f"采集线路{idx+1}"
                    play_url = s.get("vod_play_url") or ""
                    if play_url:
                        # 若單個站點有多條線路，拆開加入
                        from_parts = site_name.split("$$$")
                        url_parts = play_url.split("$$$")
                        for f_name, u_str in zip(from_parts, url_parts):
                            results.append((f"{f_name}", u_str))
        except Exception:
            pass
        return results

    def _fallback_discover(self, tid, page, extend):
        """
        當直接API無法訪問時的備援邏輯：
        1. 嘗試抓取頁面內嵌初始狀態或動態提取前端配置
        2. 若有配置 tmdb_key，直接調用 TMDB Discover API 實現完整篩選
        """
        if not self.config.get("tmdb_key"):
            try:
                html = requests.get(self.host, headers=self.headers, timeout=6).text
                key_match = re.search(r'["\']?tmdb[_a-zA-Z]*Key["\']?\s*[:=]\s*["\']([a-f0-9]{32})["\']', html, re.I)
                if key_match:
                    self.config["tmdb_key"] = key_match.group(1)
            except Exception:
                pass

        tmdb_key = self.config.get("tmdb_key")
        if not tmdb_key:
            return []

        media = "movie" if tid == "movie" else "tv"
        url = f"{self.config['tmdb_api']}/discover/{media}"
        params = {
            "api_key": tmdb_key,
            "language": "zh-CN",
            "page": page,
            "sort_by": extend.get("sort", "popularity.desc") if "." in extend.get("sort", "") else "popularity.desc"
        }

        # 處理特定頻道預設過濾條件
        if tid == "anime":
            params["with_genres"] = "16"
        elif tid == "variety":
            params["with_genres"] = "10764"
        elif extend.get("class"):
            params["with_genres"] = extend["class"]

        if extend.get("area") and extend["area"] != "OTHER":
            params["with_origin_country"] = extend["area"]

        year = extend.get("year", "")
        if year and year.isdigit():
            if media == "movie":
                params["primary_release_year"] = year
            else:
                params["first_air_date_year"] = year

        try:
            resp = requests.get(url, params=params, timeout=8)
            if resp.status_code == 200:
                items = resp.json().get("results", [])
                return [self._format_vod_item(i, media) for i in items]
        except Exception:
            pass

        return []

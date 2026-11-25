# -*- coding: utf-8 -*-
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, unquote, urljoin
from base.spider import Spider as BaseSpider


class Spider(BaseSpider):
    PAGE_SIZE = 10
    CACHE_TTL = 300  # 静态元数据缓存 5 分钟（磁力链不缓存）

    def __init__(self):
        super().__init__()
        self.host = "https://m.yysub.cc"
        self.relay = ""
        self._cache = {}
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": "https://m.yysub.cc/",
            "client": "6",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        self.classes = [
            {"type_id": "", "type_name": "全部"},
            {"type_id": "tv", "type_name": "电视剧"},
            {"type_id": "movie", "type_name": "电影"},
            {"type_id": "openclass", "type_name": "公开课"},
        ]

    def getName(self):
        return "人人影视"

    def getDependence(self):
        return []

    def init(self, extend=""):
        ext = {}
        try:
            if isinstance(extend, str) and extend.strip().startswith("{"):
                ext = json.loads(extend)
            elif isinstance(extend, dict):
                ext = extend
        except Exception:
            ext = {}

        if isinstance(ext, dict):
            if ext.get("host"):
                self.host = str(ext["host"]).strip().rstrip("/")
                self.headers["Referer"] = self.host + "/"
            if ext.get("ua"):
                self.headers["User-Agent"] = str(ext["ua"]).strip()
            if ext.get("relay"):
                self.relay = str(ext["relay"]).strip().rstrip("/")
        return None

    # ==================== 工具与缓存 ====================
    def _get_cache(self, key):
        item = self._cache.get(key)
        if item and (time.time() - item[0] < self.CACHE_TTL):
            return item[1]
        self._cache.pop(key, None)
        return None

    def _set_cache(self, key, value):
        # 限制缓存条目数，防止长时间运行内存膨胀
        if len(self._cache) > 100:
            self._cache.clear()
        self._cache[key] = (time.time(), value)

    @staticmethod
    def _safe_int(val, default=1):
        try:
            res = int(val)
            return res if res >= 1 else default
        except Exception:
            return default

    # ==================== 网络 ====================
    def _api(self, path, params=None):
        url = f"{self.host}/api/{path.lstrip('/')}"
        q = {k: v for k, v in (params or {}).items() if v not in (None, "")} or None
        net = getattr(self, "net", None)
        if net is not None:
            opts = {"headers": self.headers, "timeout": 15000}
            if q:
                opts["params"] = q
            res = net.json(url, opts)
            if not isinstance(res, dict):
                raise ValueError("无效 JSON 响应")
            return res

        rsp = self.fetch(url, params=q, headers=self.headers, timeout=15)
        code = int(getattr(rsp, "status_code", 0) or 0)
        if not (200 <= code < 300):
            raise ValueError(f"HTTP {code}")
        try:
            return json.loads(rsp.text)
        except Exception:
            raise ValueError("无效 JSON")

    def _pic(self, u):
        if not u:
            return ""
        if u.startswith("http"):
            return u
        # 兼容 https://m.yysub.cc、https://www.yysub.cc 或 https://yysub.cc 转换为 https://ftp.yysub.cc
        ftp_host = re.sub(r"^(https?://)(?:m\.|www\.)?", r"\1ftp.", self.host)
        return urljoin(ftp_host + "/", u)

    # ==================== 列表卡片 ====================
    def _card(self, i):
        if not isinstance(i, dict):
            return {}
        if isinstance(i.get("resource_info"), dict):
            i = i["resource_info"]

        rid = i.get("id") or i.get("itemid") or i.get("rid")
        name = (i.get("cnname") or i.get("title") or "").strip()
        if rid in (None, "") or not name:
            return {}

        poster = i.get("poster") or (i.get("poster_map") or {}).get("b") or i.get("poster_b") or ""
        remark = (i.get("play_status") or "").strip()
        score = i.get("score")
        try:
            if score not in (None, "", 0) and float(score) > 0:
                remark = f"{remark} {score}分".strip()
        except Exception:
            pass

        vod = {
            "vod_id": str(rid),
            "vod_name": name,
            "vod_pic": self._pic(poster),
            "vod_remark": remark,
        }
        for src_k, dst_k in (("publish_year", "vod_year"), ("area", "vod_area"), ("category", "vod_class")):
            if i.get(src_k):
                vod[dst_k] = str(i[src_k])
        return vod

    def _build_vod_list(self, raw_list):
        vods = []
        for item in raw_list or []:
            vod = self._card(item)
            if vod:
                vods.append(vod)
        return vods

    def _page(self, items, pg):
        return {
            "page": pg,
            "pagecount": pg + 1 if len(items) >= self.PAGE_SIZE else pg,
            "limit": self.PAGE_SIZE,
            "list": items,
        }

    # ==================== 首页 ====================
    def homeContent(self, filter):
        return {"class": self.classes}

    def homeVideoContent(self):
        cached = self._get_cache("home_video")
        if cached is not None:
            return cached

        vods = []
        try:
            data = self._api("index")
            vods = self._build_vod_list(data.get("resource_hot"))
        except Exception:
            vods = []

        if not vods:
            top = self._api("resource_top", {"channel": "tv_week", "limit": self.PAGE_SIZE})
            vods = self._build_vod_list(top.get("data"))

        res = {"list": vods[:self.PAGE_SIZE]}
        if vods:
            self._set_cache("home_video", res)
        return res

    # ==================== 分类 ====================
    def categoryContent(self, tid, pg, filter, extend):
        pg_num = self._safe_int(pg, 1)
        data = self._api("resource", {"p": pg_num, "channel": tid})
        vods = self._build_vod_list(data.get("list"))
        return self._page(vods, pg_num)

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        pg_num = self._safe_int(pg, 1)
        kw = (key or "").strip()
        if not kw:
            return self._page([], pg_num)
        data = self._api("search", {"keyword": kw, "type": "resource", "p": pg_num})
        vods = self._build_vod_list(data.get("data"))
        return self._page(vods, pg_num)

    # ==================== 详情 ====================
    @staticmethod
    def _se_tuple(it):
        try:
            return int(it.get("season") or 0), int(it.get("episode") or 0)
        except Exception:
            return 0, 0

    def _ep_name(self, it, channel):
        size = (it.get("size") or "").strip()
        if channel == "tv":
            s, e = self._se_tuple(it)
            if e > 0:
                name = f"S{s:02d}E{e:02d}"
            else:
                name = (f"S{s:02d} " if s > 0 else "") + "合集"
        else:
            name = (it.get("format") or "资源").strip()
        return f"{name} {size}".strip()

    def detailContent(self, ids):
        rid = str(ids[0]).strip() if ids else ""
        if not rid:
            return {"list": []}

        cache_key = f"detail_{rid}"
        cached = self._get_cache(cache_key)
        if cached is not None:
            return cached

        # 并发请求详情与资源列表，降低详情页等待时间
        with ThreadPoolExecutor(max_workers=2) as pool:
            f_det = pool.submit(self._api, f"resource/{rid}")
            f_items = pool.submit(self._api, "resource_item", {"rid": rid})
            det = f_det.result()
            items_resp = f_items.result()

        data = det.get("data") or {}
        channel = str(data.get("channel") or "")
        vod = {
            "vod_id": rid,
            "vod_name": (data.get("cnname") or "").strip(),
            "vod_pic": self._pic(data.get("poster") or (data.get("poster_map") or {}).get("b") or ""),
            "vod_content": ((data.get("detail") or {}).get("content") or "").strip(),
        }

        field_map = {
            "enname": "vod_en",
            "aliasname": "vod_sub",
            "areas": "vod_area",
            "lang": "vod_lang",
            "category": "vod_class",
            "publish_year": "vod_year",
            "premiere": "vod_time",
            "play_status": "vod_remark",
        }
        for src_k, dst_k in field_map.items():
            if data.get(src_k):
                vod[dst_k] = str(data[src_k])

        sc = det.get("score") or {}
        if isinstance(sc, dict) and sc.get("score"):
            vod["vod_score"] = str(sc["score"])

        actors = [c.get("cnname") for c in (det.get("character_list") or []) if c.get("cnname")]
        if actors:
            vod["vod_actor"] = "/".join(actors[:12])

        items_data = items_resp.get("data") or {}
        raw_items = [it for it in (items_data.get("item_list") or []) if it.get("id")]
        # 按季数与集数升序排列，避免多季剧集乱序
        raw_items.sort(key=self._se_tuple)

        # 批量获取夸克网盘链接
        pan_map = {}
        item_ids = [str(it["id"]) for it in raw_items]
        if item_ids:
            try:
                pan_data = self._api(
                    "resource_link",
                    {"itemid": ",".join(item_ids), "way": 9, "action": "batch"},
                ).get("data") or []
                for iid, addr in zip(item_ids, pan_data):
                    addr = (addr or "").strip()
                    if addr:
                        pan_map[iid] = addr
            except Exception:
                pan_map = {}

        lines = {}
        pan_eps = []
        for it in raw_items:
            iid = str(it["id"])
            fmt = (it.get("format") or "磁力").strip() or "磁力"
            name = self._ep_name(it, channel)
            lines.setdefault(fmt, []).append(f"{name}${iid}")
            if iid in pan_map:
                # 直接将已获取的网盘 URL 编码带入播放参数，避免点击播放时二次请求
                pan_eps.append(f"{name}$quark:{iid}|{quote(pan_map[iid], safe='')}")

        sources = []
        urls = []
        for fmt in sorted(lines.keys()):
            sources.append(f"{fmt} 磁力")
            urls.append("#".join(lines[fmt]))
        if pan_eps:
            sources.append("夸克网盘")
            urls.append("#".join(pan_eps))

        vod["vod_play_from"] = "$$$".join(sources) if sources else "磁力"
        vod["vod_play_url"] = "$$$".join(urls)

        res = {"list": [vod]}
        self._set_cache(cache_key, res)
        return res

    # ==================== 播放 ====================
    def _magnet_addrs(self, itemid):
        data = self._api("resource_item_file", {"itemid": str(itemid)}).get("data") or []
        fallback = ""
        for f in data:
            a = (f.get("address") or "").strip()
            if not a:
                continue
            if str(f.get("way") or "") == "2" and a.startswith("magnet:"):
                return a
            if not fallback:
                fallback = a
        return fallback

    def _pan_addr(self, itemid):
        data = self._api(
            "resource_link",
            {"itemid": str(itemid), "way": 9, "action": "batch"},
        ).get("data") or []
        for a in data:
            a = (a or "").strip()
            if a:
                return a
        return ""

    def playerContent(self, flag, id, vipFlags):
        pid = str(id)
        ua_header = {"User-Agent": self.headers["User-Agent"]}

        if pid.startswith("quark:"):
            payload = pid[len("quark:"):]
            if "|" in payload:
                itemid, encoded_url = payload.split("|", 1)
                pan_url = unquote(encoded_url) or self._pan_addr(itemid)
            else:
                pan_url = self._pan_addr(payload)
            return {"parse": 1, "url": pan_url, "header": ua_header}

        addr = self._magnet_addrs(pid)
        if self.relay and addr.startswith("magnet:"):
            play_url = f"{self.relay}/play?link={quote(addr, safe='')}"
        else:
            play_url = addr
        return {"parse": 0, "url": play_url, "header": ua_header}

    def localProxy(self, param):
        pass

    def destroy(self):
        self._cache.clear()

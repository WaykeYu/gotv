# -*- coding: utf-8 -*-
"""
红果短剧 (hongguo / www.hongguoapp.cn) —— 详情页可视化诊断版
直接将各 API 与播放页的实际抓包结果输出到详情页【简介】中，无需找日志文件。
"""
import re
import sys
import json
import time
import base64
import requests
from requests.adapters import HTTPAdapter
from urllib.parse import quote, unquote, urljoin
from lxml import etree

try:
    import urllib3
    urllib3.disable_warnings()
except Exception:
    pass

sys.path.append('..')
try:
    from base.spider import Spider as BaseSpider
except Exception:
    from spider import Spider as BaseSpider


class Spider(BaseSpider):
    _RE_TID = re.compile(r"/(?:vodshow|vodtype|type|show/id|type/id)/(\d+)")
    _RE_VID = re.compile(r"/(?:voddetail|detail/id|vod/detail/id)/(\d+)|/id/(\d+)\.html")
    _RE_PLAYER_JSON = re.compile(r'player_[a-z0-9_]+\s*=\s*(\{.*?\})\s*(?:;|</script>)', re.S)
    _RE_M3U8 = re.compile(r'(https?[^"\'\s\\<>]+\.m3u8[^"\'\s\\<>]*)')
    _RE_MP4 = re.compile(r'(https?[^"\'\s\\<>]+\.mp4[^"\'\s\\<>]*)')

    _VIRTUAL_CATS = [
        ("51", "全部短剧"),
        ("51:都市", "都市"),
        ("51:古装", "古装"),
        ("51:逆袭", "逆袭"),
        ("51:甜宠", "甜宠"),
        ("51:战神", "战神"),
        ("51:重生", "重生"),
        ("51:总裁", "总裁"),
        ("51:家庭", "家庭"),
    ]

    def getName(self):
        return "红果"

    def init(self, extend=""):
        self.host = "https://www.hongguoapp.cn"
        try:
            o = json.loads(extend) if extend else {}
            if isinstance(o, dict) and o.get("host"):
                self.host = o["host"].rstrip("/")
        except Exception:
            pass

        self.ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": self.host + "/",
        }
        self._sess = requests.Session()
        self._sess.headers.update(self.headers)

    def _fix(self, u):
        if not u:
            return ""
        u = str(u).strip().replace("\\/", "/")
        if u.startswith("//"):
            return "https:" + u
        if u.startswith("/"):
            return self.host + u
        return u

    def homeContent(self, filter):
        cls = [{"type_id": cid, "type_name": cname} for cid, cname in self._VIRTUAL_CATS]
        cat_res = self.categoryContent("51", 1, False, {})
        return {"class": cls, "list": cat_res.get("list", []), "filters": {}}

    def homeVideoContent(self):
        return {"list": self.categoryContent("51", 1, False, {}).get("list", [])}

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg or 1)
        raw_tid = str(tid or "51")
        real_tid, sub_class = raw_tid.split(":", 1) if ":" in raw_tid else (raw_tid, "")
        url = f"{self.host}/index.php/ajax/data?mid=1&limit=24&tid={quote(real_tid)}"
        if pg > 1:
            url += f"&page={pg}"
        if sub_class:
            url += f"&class={quote(sub_class)}"

        items = []
        try:
            r = self._sess.get(url, timeout=8, verify=False)
            j = r.json()
            for it in (j.get("list") or []):
                vid = str(it.get("vod_id") or "")
                name = str(it.get("vod_name") or "").strip()
                if vid and name:
                    items.append({
                        "vod_id": vid,
                        "vod_name": name,
                        "vod_pic": self._fix(it.get("vod_pic") or ""),
                        "vod_remarks": str(it.get("vod_remarks") or "").strip(),
                    })
            pc = int(j.get("pagecount") or pg)
            return {"page": pg, "pagecount": pc, "limit": 24, "total": pc * 24, "list": items}
        except Exception:
            return {"page": pg, "pagecount": pg, "limit": 24, "total": 0, "list": []}

    def detailContent(self, ids):
        vid = str(ids[0]) if ids else ""
        if not vid:
            return {"list": []}

        diag = []
        vod_name = f"测试短剧_{vid}"
        vod_pic = ""
        play_from = "红果"
        play_url = f"第1集${self.host}/vodplay/{vid}-1-1.html"

        # 依次探测 4 个端点，记录实际状态码与返回前 120 字
        test_urls = [
            ("videolist", f"{self.host}/api.php/provide/vod/?ac=videolist&ids={vid}"),
            ("detail_api", f"{self.host}/api.php/provide/vod/?ac=detail&ids={vid}"),
            ("ajax_detail", f"{self.host}/index.php/ajax/detail?mid=1&id={vid}"),
            ("play_page", f"{self.host}/vodplay/{vid}-1-1.html"),
        ]

        for tag, u in test_urls:
            try:
                r = self._sess.get(u, timeout=6, verify=False)
                r.encoding = "utf-8"
                txt = (r.text or "").strip().replace("\n", " ")
                diag.append(f"[{tag}] HTTP {r.status_code} | len={len(txt)} | {txt[:140]}")

                # 如果接口直接返回了真实播放数据，顺便提取
                if r.status_code == 200 and txt.startswith("{"):
                    j = json.loads(txt)
                    item = None
                    if isinstance(j.get("list"), list) and j["list"]:
                        item = j["list"][0]
                    elif isinstance(j.get("info"), dict):
                        item = j["info"]
                    if item:
                        vod_name = item.get("vod_name") or vod_name
                        vod_pic = self._fix(item.get("vod_pic") or "")
                        if item.get("vod_play_url"):
                            play_from = item.get("vod_play_from") or "红果"
                            play_url = item["vod_play_url"]
            except Exception as e:
                diag.append(f"[{tag}] ERR: {repr(e)[:80]}")

        return {
            "list": [{
                "vod_id": vid,
                "vod_name": vod_name,
                "vod_pic": vod_pic,
                "vod_content": "\n".join(diag),
                "vod_play_from": play_from,
                "vod_play_url": play_url,
            }]
        }

    def searchContent(self, key, quick, pg="1"):
        q = quote(str(key or "").strip())
        if not q:
            return {"list": [], "page": 1}
        try:
            r = self._sess.get(f"{self.host}/index.php/ajax/suggest?mid=1&wd={q}&limit=60", timeout=6, verify=False)
            j = r.json()
            items = [
                {"vod_id": str(it["id"]), "vod_name": str(it["name"]), "vod_pic": self._fix(it.get("pic") or "")}
                for it in (j.get("list") or []) if it.get("id") and it.get("name")
            ]
            return {"list": items, "page": 1}
        except Exception:
            return {"list": [], "page": 1}

    def searchContentPage(self, key, quick, page):
        return self.searchContent(key, quick, page)

    def playerContent(self, flag, id, vipFlags):
        return {"parse": 0, "url": id}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def localProxy(self, param):
        return None

    def getDependence(self):
        return []

    def destroy(self):
        try:
            self._sess.close()
        except Exception:
            pass
        return None

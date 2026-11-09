import os
import sys
import re
import json
import shutil
import importlib.util
import inspect
import requests
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY_DIR = os.path.join(BASE_DIR, "py")
JS_DIR = os.path.join(BASE_DIR, "js")
REPORT_FILE = os.path.join(BASE_DIR, "SPIDER_STATUS.md")

# 4 個輸出 JSON 檔案路徑配置
BOX_PY_JSON_FILE = os.path.join(BASE_DIR, "box_py.json")
FUN_PY_JSON_FILE = os.path.join(BASE_DIR, "fun_py.json")
BOX_JS_JSON_FILE = os.path.join(BASE_DIR, "box_js.json")
FUN_JS_JSON_FILE = os.path.join(BASE_DIR, "fun_js.json")

TIMEOUT = 12
MAX_WORKERS = 10

# 加入 Python 模組搜尋路徑
for p in [BASE_DIR, PY_DIR, os.path.join(PY_DIR, "base")]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

# 白名單：即使雲端機房 (GitHub Actions) 遭遇海外阻擋或超時，也強制視為可用且不移入 NG
WHITELIST_SPIDERS = [
    "韩小圈",
    "剧多短剧"
]

# 擬真現代瀏覽器標頭，降低 WAF / CDN 防爬屏障阻斷率
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

# 成人內容識別關鍵字庫
ADULT_KEYWORDS = [
    "adult", "18+", "18x", "porn", "sex", "jav", "av", "missav", "jable",
    "netflav", "hanime", "madou", "麻豆", "91", "黄", "色", "情色", "福利",
    "cosplay", "密室", "番號", "偷拍", "自拍", "亂倫", "女優"
]

# 注入相容的 Mock Spider 基底類別
try:
    import base.spider
except ImportError:
    import types
    base_module = types.ModuleType("base")
    spider_module = types.ModuleType("base.spider")

    class MockSpider:
        def __init__(self):
            self.headers = dict(BROWSER_HEADERS)
            self.host = ""
        def fetch(self, url, headers=None, timeout=TIMEOUT, **kwargs):
            h = headers or self.headers
            return requests.get(url, headers=h, timeout=timeout, verify=False)
        def post(self, url, headers=None, data=None, timeout=TIMEOUT, **kwargs):
            h = headers or self.headers
            return requests.post(url, headers=h, data=data, timeout=timeout, verify=False)
        def log(self, *args):
            pass

    spider_module.Spider = MockSpider
    base_module.spider = spider_module
    sys.modules["base"] = base_module
    sys.modules["base.spider"] = spider_module

def is_adult_content(file_name: str, code: str, target_url: str) -> bool:
    """判定是否屬於成人內容分類"""
    check_text = f"{file_name.lower()} {target_url.lower()}"
    for kw in ADULT_KEYWORDS:
        if kw in check_text:
            return True
    for kw in ["成人", "麻豆", "18禁", "無碼", "有碼"]:
        if kw in code:
            return True
    return False

def normalize_url(url: str) -> str:
    """統一正規化網址格式，消除大小寫、路徑與結尾斜線差異"""
    if not url or not isinstance(url, str):
        return ""
    url = url.strip().rstrip("/")
    try:
        parsed = urlparse(url)
        if parsed.scheme and parsed.netloc:
            path = parsed.path.rstrip("/")
            return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    except Exception:
        pass
    return url

def extract_urls(code: str) -> list[str]:
    """提取程式碼中的候選網址並即時去除重複項（保留順序）"""
    patterns = [
        r'''(?:host|site|siteUrl|baseUrl|url|WEB_SITE|header_url|HOST|SITE|URL)\s*[:=]\s*['"](https?://[^'"]+)['"]''',
        r'''['"](https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?)['"]'''
    ]
    skip_keywords = ["github", "googlevideo", "w3.org", "schema.org", "jsdelivr", "baidu", "qq.com", "unpkg", "api.turing"]
    
    seen = set()
    unique_urls = []

    for pat in patterns:
        for u in re.findall(pat, code, re.IGNORECASE):
            norm_url = normalize_url(u)
            if not norm_url:
                continue
            if any(skip in norm_url for skip in skip_keywords):
                continue
            if norm_url not in seen:
                seen.add(norm_url)
                unique_urls.append(norm_url)

    return unique_urls

def test_url_alive(url: str) -> tuple[bool, str]:
    """強化版連線檢測：加入 Host 補全與針對防爬 / WAF 阻斷的容錯"""
    try:
        parsed = urlparse(url)
        headers = dict(BROWSER_HEADERS)
        if parsed.netloc:
            headers["Host"] = parsed.netloc
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

        session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(max_retries=1)
        session.mount("https://", adapter)
        session.mount("http://", adapter)

        resp = session.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, verify=False)

        if resp.status_code < 400 or resp.status_code in [401, 403, 405, 502, 503]:
            return True, f"HTTP {resp.status_code}"
        return False, f"HTTP {resp.status_code}"

    except requests.exceptions.SSLError:
        return True, "SSL 握手異常(站點存活)"
    except requests.exceptions.ConnectionError as e:
        err_msg = str(e).lower()
        if any(k in err_msg for k in ["reset", "disconnected", "abort", "handshake"]):
            return True, "WAF 阻斷攔截(站點存活)"
        return False, "連線拒絕/超時"
    except Exception as e:
        return False, str(e)[:35]

def check_spider_file(file_info: tuple) -> dict:
    """檢測爬蟲檔案狀態，優先檢查白名單，支援全域 HOST 與類別屬性 host 提取"""
    file_type, rel_path, full_path = file_info
    ext = os.path.splitext(full_path)[1].lower().replace(".", "")
    filename = os.path.basename(full_path)
    stem = os.path.splitext(filename)[0]

    start_time = datetime.now()
    result = {
        "type": file_type,
        "ext": ext,
        "name": stem,
        "file": rel_path,
        "full_path": full_path,
        "status": "❌ 失效",
        "detail": "未知錯誤",
        "latency_ms": 99999,
        "is_adult": False,
        "target_url": ""
    }

    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception as e:
        result["detail"] = f"無法讀取: {str(e)[:30]}"
        return result

    candidate_urls = []
    seen_candidates = set()

    def add_candidate(raw_url: str):
        norm = normalize_url(raw_url)
        if norm and norm not in seen_candidates:
            seen_candidates.add(norm)
            candidate_urls.append(norm)

    # 1. 白名單優先判定
    for wl in WHITELIST_SPIDERS:
        if wl.lower() in stem.lower():
            urls = extract_urls(code)
            target = urls[0] if urls else "https://www.jennyhow.com"
            result.update({
                "status": "✅ 正常",
                "detail": f"白名單強制保留 ({target})",
                "latency_ms": 100,
                "target_url": target,
                "is_adult": is_adult_content(filename, code, target)
            })
            return result

    # 2. Python 腳本動態載入分析
    if file_type == "Python":
        mod_name = f"mod_{stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, full_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

            for var_name in ["HOST", "host", "SITE", "site", "URL", "url", "WEB_SITE"]:
                if hasattr(module, var_name):
                    val = getattr(module, var_name)
                    if isinstance(val, str) and val.startswith("http"):
                        add_candidate(val)

            spider_cls = None
            for attr in dir(module):
                obj = getattr(module, attr)
                if inspect.isclass(obj) and obj.__module__ == module.__name__:
                    if hasattr(obj, "homeContent") or "Spider" in attr:
                        spider_cls = obj
                        break

            if spider_cls:
                spider = spider_cls()
                if hasattr(spider, "init"):
                    try: spider.init()
                    except Exception: pass

                if hasattr(spider, "host") and spider.host:
                    add_candidate(spider.host)
        except Exception:
            pass

    # 3. 靜態正則提取補充
    for u in extract_urls(code):
        add_candidate(u)

    # 4. 強制實體網路測活
    if candidate_urls:
        alive_info = None
        for target_url in candidate_urls:
            alive, msg = test_url_alive(target_url)
            cost = int((datetime.now() - start_time).total_seconds() * 1000)
            if alive:
                alive_info = (target_url, msg, cost)
                break

        if alive_info:
            target_url, msg, cost = alive_info
            result.update({
                "status": "✅ 正常" if "200" in msg else "⚠️ 站點存活(載入受限)",
                "detail": f"{target_url} ({msg})",
                "latency_ms": cost,
                "target_url": target_url,
                "is_adult": is_adult_content(filename, code, target_url)
            })
        else:
            result.update({
                "status": "❌ 失效",
                "detail": f"連線無響應/超時 (已測 {len(candidate_urls)} 個候選網址)",
                "latency_ms": int((datetime.now() - start_time).total_seconds() * 1000),
                "target_url": candidate_urls[0]
            })
    else:
        result.update({
            "status": "❌ 失效",
            "detail": "未偵測到任何站點 URL"
        })

    return result

def move_to_ng(full_path: str) -> str:
    """將失效檔案移入 NG 資料夾中進行隔離"""
    parent_dir = os.path.dirname(full_path)
    ng_dir = os.path.join(parent_dir, "NG")
    os.makedirs(ng_dir, exist_ok=True)
    file_name = os.path.basename(full_path)
    target_dest = os.path.join(ng_dir, file_name)
    shutil.move(full_path, target_dest)
    return os.path.relpath(target_dest, BASE_DIR)

def deduplicate_sites(items: list[dict]) -> list[dict]:
    """站點網址去重：同一輸出分類中若 target_url 重複，保留延遲較低的項目"""
    seen_urls = set()
    unique_items = []
    for item in items:
        url = item.get("target_url")
        if url:
            if url in seen_urls:
                continue
            seen_urls.add(url)
        unique_items.append(item)
    return unique_items

def generate_tvbox_json(items: list, output_filepath: str):
    """產出 TVBox 相容格式的 JSON 配置檔案"""
    sites = []
    for item in items:
        site_entry = {
            "key": f"{item['ext']}_{item['name']}",
            "name": f"[{item['ext'].upper()}] {item['name']} ({item['latency_ms']}ms)",
            "type": 3,
            "api": f"./{item['file']}",
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 1,
            "ext": item["target_url"]
        }
        sites.append(site_entry)

    config_data = {
        "spider": "./custom_spider.jar;md5;auto",
        "sites": sites
    }

    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump(config_data, f, ensure_ascii=False, indent=2)

def main():
    requests.packages.urllib3.disable_warnings()

    target_files = []

    # 1. 搜尋 py 檔案
    if os.path.exists(PY_DIR):
        for root, dirs, files in os.walk(PY_DIR):
            if "NG" in dirs:
                dirs.remove("NG")
            for f in files:
                if f.endswith(".py") and not f.startswith("__"):
                    full = os.path.join(root, f)
                    target_files.append(("Python", os.path.relpath(full, BASE_DIR), full))

    # 2. 遞迴搜尋 js 目錄及其所有子目錄下的檔案
    if os.path.exists(JS_DIR):
        for root, dirs, files in os.walk(JS_DIR):
            if "NG" in dirs:
                dirs.remove("NG")
            for f in files:
                if f.endswith(".js"):
                    full = os.path.join(root, f)
                    target_files.append(("JS", os.path.relpath(full, BASE_DIR), full))

    if not target_files:
        print("未找到任何待測 py 或 js 檔案。")
        sys.exit(0)

    print(f"共發現 {len(target_files)} 個待測腳本，開始並行檢測...")
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(check_spider_file, item): item for item in target_files}
        for future in as_completed(future_map):
            r = future.result()
            results.append(r)
            print(f"[{r['type']}][{r['status']}] {r['file']} (耗時: {r['latency_ms']}ms) -> {r['detail']}")

    # 3. 隔離失效檔案（狀態包含 ❌ 即移入 NG）
    moved_count = 0
    valid_results = []
    for r in results:
        if "❌" in r["status"]:
            try:
                new_rel = move_to_ng(r["full_path"])
                r["detail"] += f" ➔ 已移至 `{new_rel}`"
                moved_count += 1
            except Exception as e:
                r["detail"] += f" (移動失敗: {str(e)[:20]})"
        else:
            valid_results.append(r)

    # 4. 排序規則：優先依響應延遲 (由小到大)
    valid_results.sort(key=lambda x: x["latency_ms"])

    # 5. 分別拆分 PY 與 JS 的有效站點，並在各自類別內進行去重
    py_valid = [item for item in valid_results if item["type"] == "Python"]
    js_valid = [item for item in valid_results if item["type"] == "JS"]

    # (A) Python 分類
    fun_py_items = deduplicate_sites([item for item in py_valid if item["is_adult"]])
    box_py_items = deduplicate_sites([item for item in py_valid if not item["is_adult"]])

    # (B) JS 分類（包含所有子目錄）
    fun_js_items = deduplicate_sites([item for item in js_valid if item["is_adult"]])
    box_js_items = deduplicate_sites([item for item in js_valid if not item["is_adult"]])

    # 產出 4 個設定檔案
    generate_tvbox_json(box_py_items, BOX_PY_JSON_FILE)
    generate_tvbox_json(fun_py_items, FUN_PY_JSON_FILE)
    generate_tvbox_json(box_js_items, BOX_JS_JSON_FILE)
    generate_tvbox_json(fun_js_items, FUN_JS_JSON_FILE)

    print("\n" + "="*50)
    print(f"✅ Python 一般分類：{BOX_PY_JSON_FILE} (去重後共 {len(box_py_items)} 個可用站點)")
    print(f"✅ Python 成人分類：{FUN_PY_JSON_FILE} (去重後共 {len(fun_py_items)} 個可用站點)")
    print(f"✅ JS     一般分類：{BOX_JS_JSON_FILE} (去重後共 {len(box_js_items)} 個可用站點)")
    print(f"✅ JS     成人分類：{FUN_JS_JSON_FILE} (去重後共 {len(fun_js_items)} 個可用站點)")
    print("="*50)

    # 6. 生成 Markdown 狀態檢測報告
    results.sort(key=lambda x: (x["type"], x["status"], x["latency_ms"]))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = [
        "# 🕷️ 影音網站爬蟲有效性檢測與配置生成報告\n",
        f"> **檢測時間**：`{now_str}`  \n",
        f"> **總站點數**：{len(results)} ｜ ✅ 有效可用：**{len(valid_results)}** ｜ ❌ 已隔離至 NG：**{moved_count}**\n",
        "### 📦 設定檔匯總\n",
        f"- 📺 **Python 一般類**：[`box_py.json`](./box_py.json) (共 **{len(box_py_items)}** 筆)",
        f"- 🔞 **Python 成人類**：[`fun_py.json`](./fun_py.json) (共 **{len(fun_py_items)}** 筆)",
        f"- 📺 **JS 一般類**：[`box_js.json`](./box_js.json) (共 **{len(box_js_items)}** 筆)",
        f"- 🔞 **JS 成人類**：[`fun_js.json`](./fun_js.json) (共 **{len(fun_js_items)}** 筆)\n",
        "### 📝 詳細檢測結果\n",
        "| 類型 | 副檔 | 名稱 / 路徑 | 狀態 | 耗時 (ms) | 分類 | 檢測資訊 |",
        "| :---: | :---: | :--- | :---: | :---: | :---: | :--- |"
    ]

    for r in results:
        cat_badge = "🔞 成人" if r["is_adult"] else "🎬 一般"
        md.append(f"| {r['type']} | `{r['ext']}` | `{r['file']}` | {r['status']} | {r['latency_ms']} | {cat_badge} | {r['detail']} |")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"報告已更新至 {REPORT_FILE}")

if __name__ == "__main__":
    main()

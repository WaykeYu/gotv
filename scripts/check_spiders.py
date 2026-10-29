import os
import sys
import re
import json
import shutil
import importlib.util
import inspect
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# BASE_DIR 即為專案根目錄（主目錄）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY_DIR = os.path.join(BASE_DIR, "py")
JS_DIR = os.path.join(BASE_DIR, "js")

# 輸出檔案皆設定在主目錄下
BOX_JSON_FILE = os.path.join(BASE_DIR, "box_py.json")
FUN_JSON_FILE = os.path.join(BASE_DIR, "fun_py.json")
REPORT_FILE = os.path.join(BASE_DIR, "SPIDER_STATUS.md")

TIMEOUT = 12
MAX_WORKERS = 10

# 加入 Python 模組搜尋路徑
for p in [BASE_DIR, PY_DIR, os.path.join(PY_DIR, "base")]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7"
}

# 成人分類關鍵字庫
ADULT_KEYWORDS = [
    "adult", "18+", "18x", "porn", "sex", "jav", "av", "missav", "jable",
    "netflav", "hanime", "madou", "麻豆", "91", "黄", "色", "情色", "福利",
    "cosplay", "密室", "番號", "偷拍", "自拍", "女優"
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
    check_text = f"{file_name.lower()} {target_url.lower()}"
    for kw in ADULT_KEYWORDS:
        if kw in check_text:
            return True
    for kw in ["成人", "麻豆", "18禁", "無碼", "有碼"]:
        if kw in code:
            return True
    return False

def extract_urls(code: str) -> list:
    patterns = [
        r'''(?:host|site|siteUrl|baseUrl|url|WEB_SITE|header_url)\s*[:=]\s*['"](https?://[^'"]+)['"]''',
        r'''['"](https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?)['"]'''
    ]
    urls = []
    skip_keywords = ["github", "googlevideo", "w3.org", "schema.org", "jsdelivr", "baidu", "qq.com", "unpkg", "api.turing"]
    for pat in patterns:
        for u in re.findall(pat, code, re.IGNORECASE):
            u_clean = u.rstrip("/")
            if not any(skip in u_clean.lower() for skip in skip_keywords) and u_clean not in urls:
                urls.append(u_clean)
    return urls

def test_url_alive(url: str) -> tuple[bool, str]:
    try:
        headers = dict(BROWSER_HEADERS)
        headers["Referer"] = url + "/"
        resp = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, verify=False)
        if resp.status_code < 400 or resp.status_code in [403, 503]:
            return True, f"HTTP {resp.status_code}"
        return False, f"HTTP {resp.status_code}"
    except requests.exceptions.SSLError:
        return True, "SSL 驗證失敗 (站點存活)"
    except Exception as e:
        return False, str(e)[:35]

def check_spider_file(file_info: tuple) -> dict:
    file_type, rel_path, full_path = file_info
    ext = os.path.splitext(full_path)[1].lower().replace(".", "")
    filename = os.path.basename(full_path)
    stem = os.path.splitext(filename)[0]

    start_time = datetime.now()
    result = {
        "type": file_type,
        "ext": ext,
        "name": stem,
        "file": rel_path.replace("\\", "/"),
        "full_path": full_path,
        "status": "❌ 異常",
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

    # 1. Python 腳本優先執行介面驗證
    if file_type == "Python":
        mod_name = f"mod_{stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, full_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

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
                    cost = int((datetime.now() - start_time).total_seconds() * 1000)
                    result.update({
                        "status": "✅ 正常",
                        "detail": f"動態取得主站: {spider.host}",
                        "latency_ms": cost,
                        "target_url": spider.host,
                        "is_adult": is_adult_content(filename, code, spider.host)
                    })
                    return result

                if hasattr(spider, "homeContent"):
                    res = spider.homeContent(True)
                    if res and isinstance(res, (dict, list, str)):
                        cost = int((datetime.now() - start_time).total_seconds() * 1000)
                        urls = extract_urls(code)
                        t_url = urls[0] if urls else ""
                        result.update({
                            "status": "✅ 正常",
                            "detail": "homeContent 響應成功",
                            "latency_ms": cost,
                            "target_url": t_url,
                            "is_adult": is_adult_content(filename, code, t_url)
                        })
                        return result
        except Exception:
            pass

    # 2. 靜態提取 URL 連線測試
    urls = extract_urls(code)
    if urls:
        alive_info = None
        for target_url in urls:
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
            result["status"] = "❌ 失效"
            result["detail"] = f"連線失敗 (測試 {len(urls)} 個候選網址)"
            result["latency_ms"] = int((datetime.now() - start_time).total_seconds() * 1000)
    else:
        result["detail"] = "未偵測到有效網站 URL"

    return result

def move_to_ng(full_path: str) -> str:
    parent_dir = os.path.dirname(full_path)
    ng_dir = os.path.join(parent_dir, "NG")
    os.makedirs(ng_dir, exist_ok=True)
    file_name = os.path.basename(full_path)
    target_dest = os.path.join(ng_dir, file_name)
    shutil.move(full_path, target_dest)
    return os.path.relpath(target_dest, BASE_DIR).replace("\\", "/")

def generate_tvbox_json(items: list, output_filepath: str):
    """產出 TVBox 訂閱 JSON 檔案到主目錄"""
    sites = []
    for item in items:
        # 依照類型判斷調用 type（py 為 3，js 通常為 3 且配合 js 引擎）
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

    # 搜尋 py 檔案
    if os.path.exists(PY_DIR):
        for root, dirs, files in os.walk(PY_DIR):
            if "NG" in dirs:
                dirs.remove("NG")
            for f in files:
                if f.endswith(".py") and not f.startswith("__"):
                    full = os.path.join(root, f)
                    target_files.append(("Python", os.path.relpath(full, BASE_DIR), full))

    # 搜尋 js 檔案
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
            print(f"[{r['type']}][{r['status']}] {r['file']} ({r['latency_ms']}ms) -> {r['detail']}")

    # 隔離失效檔案到各自目錄的 NG 資料夾
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

    # 排序規則：1. 副檔類型 (py:0, js:1) 2. 響應耗時 (由快到慢)
    ext_order = {"py": 0, "js": 1}
    valid_results.sort(key=lambda x: (ext_order.get(x["ext"], 9), x["latency_ms"]))

    # 分流為成人 (fun_py.json) 與一般 (box_py.json)
    fun_items = [item for item in valid_results if item["is_adult"]]
    box_items = [item for item in valid_results if not item["is_adult"]]

    generate_tvbox_json(fun_items, FUN_JSON_FILE)
    generate_tvbox_json(box_items, BOX_JSON_FILE)
    print(f"已產生成人類配置至主目錄：{FUN_JSON_FILE} (共 {len(fun_items)} 筆)")
    print(f"已產生一般類配置至主目錄：{BOX_JSON_FILE} (共 {len(box_items)} 筆)")

    # 產出報告至主目錄 SPIDER_STATUS.md
    results.sort(key=lambda x: (x["type"], x["status"], x["latency_ms"]))

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    md = [
        "# 🕷️ 影音網站爬蟲有效性檢測與配置生成報告\n",
        f"> **檢測時間**：`{now_str}`  \n",
        f"> **總站點數**：{len(results)} ｜ ✅ 有效可用：**{len(valid_results)}** (一般: **{len(box_items)}**, 成人: **{len(fun_items)}**) ｜ ❌ 已隔離至 NG：**{moved_count}**\n",
        "### 📦 主目錄設定檔匯總\n",
        f"- 📺 一般類影音配置：[`box_py.json`](./box_py.json) (共 **{len(box_items)}** 筆，依 py/js 及響應速度排序)",
        f"- 🔞 成人類影音配置：[`fun_py.json`](./fun_py.json) (共 **{len(fun_items)}** 筆，依 py/js 及響應速度排序)\n",
        "### 📝 詳細檢測結果\n",
        "| 類型 | 副檔 | 檔案路徑 | 狀態 | 耗時 (ms) | 分類 | 檢測資訊 |",
        "| :---: | :---: | :--- | :---: | :---: | :---: | :--- |"
    ]

    for r in results:
        cat_badge = "🔞 成人" if r["is_adult"] else "🎬 一般"
        md.append(f"| {r['type']} | `{r['ext']}` | `{r['file']}` | {r['status']} | {r['latency_ms']} | {cat_badge} | {r['detail']} |")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"檢測完成！報告已更新至主目錄 {REPORT_FILE}")

if __name__ == "__main__":
    main()

import os
import sys
import re
import json
import shutil
import importlib.util
import inspect
from pathlib import Path
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# --- 目錄與路徑設定（智慧偵測專案根目錄）---
CURRENT_DIR = Path(__file__).resolve().parent
# 如果腳本位在 scripts/ 目錄下，往上一層找根目錄；否則使用當前目錄
if CURRENT_DIR.name == "scripts":
    BASE_DIR = CURRENT_DIR.parent
else:
    BASE_DIR = CURRENT_DIR

PY_DIR = BASE_DIR / "py"
JS_DIR = BASE_DIR / "js"
REPORT_FILE = BASE_DIR / "SPIDER_STATUS.md"

BOX_PY_FILE = BASE_DIR / "box_py.json"
FUN_PY_FILE = BASE_DIR / "fun_py.json"
BOX_JS_FILE = BASE_DIR / "box_js.json"
FUN_JS_FILE = BASE_DIR / "fun_js.json"

TIMEOUT = 8
MAX_WORKERS = 16

for p in [BASE_DIR, PY_DIR, PY_DIR / "base"]:
    p_str = str(p)
    if p.exists() and p_str not in sys.path:
        sys.path.insert(0, p_str)

# 白名單：即使雲端測活異常也強制視為可用
WHITELIST_SPIDERS = {"韩小圈", "剧多短剧", "花都", "kisd"}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
}

ADULT_KEYWORDS = [
    r"18\+", r"18x", r"porn", r"jav", r"\bav\b", r"missav", r"jable",
    r"netflav", r"hanime", r"madou", r"麻豆", r"情色", r"番號", r"女優",
    r"18禁", r"無碼", r"有碼", r"成人"
]
ADULT_REGEX = re.compile("|".join(ADULT_KEYWORDS), re.IGNORECASE)

# --- Mock Spider 基底類別注入 ---
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
            return requests.get(url, headers=headers or self.headers, timeout=timeout, verify=False)
        def post(self, url, headers=None, data=None, timeout=TIMEOUT, **kwargs):
            return requests.post(url, headers=headers or self.headers, data=data, timeout=timeout, verify=False)
        def log(self, *args):
            pass

    spider_module.Spider = MockSpider
    base_module.spider = spider_module
    sys.modules["base"] = base_module
    sys.modules["base.spider"] = spider_module


def create_reusable_session() -> requests.Session:
    session = requests.Session()
    retries = Retry(total=1, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retries, pool_connections=MAX_WORKERS, pool_maxsize=MAX_WORKERS * 2)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

GLOBAL_SESSION = create_reusable_session()


def is_adult_content(file_name: str, code: str, target_url: str) -> bool:
    sample_text = f"{file_name} {target_url} {code[:2000]}"
    return bool(ADULT_REGEX.search(sample_text))


def normalize_url(url: str) -> str:
    if not url or not isinstance(url, str):
        return ""
    url = url.strip().rstrip("/")
    try:
        parsed = urlparse(url)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            path = parsed.path.rstrip("/")
            return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{path}"
    except Exception:
        pass
    return ""


def clean_test_url(raw_url: str) -> str:
    """清理帶有模板參數的網址（如 {wd}、{pg}），轉為主機根目錄進行存活測試"""
    try:
        cleaned = re.sub(r"\{.*?\}|\$.*?|@.*?", "", raw_url)
        parsed = urlparse(cleaned)
        if parsed.scheme in ("http", "https") and parsed.netloc:
            return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"
    except Exception:
        pass
    return raw_url


def extract_urls(code: str) -> list[str]:
    """深度解析 JSON 字典/列表與各類規則正則"""
    seen = set()
    unique_urls = []
    skip_domains = {"github.com", "googlevideo.com", "w3.org", "schema.org", "jsdelivr.net", "baidu.com", "qq.com", "unpkg.com"}

    def add_url(u: str):
        if not u or not isinstance(u, str):
            return
        match = re.search(r"https?://[^\s'\"<>\\]+", u)
        if match:
            raw = match.group(0).rstrip(";/")
            norm = normalize_url(raw)
            if norm:
                parsed = urlparse(norm)
                if not any(domain in parsed.netloc for domain in skip_domains):
                    if norm not in seen:
                        seen.add(norm)
                        unique_urls.append(norm)

    # 1. 深度遍歷結構化 JSON
    try:
        data = json.loads(code)
        def recurse_json(node):
            if isinstance(node, dict):
                for v in node.values():
                    if isinstance(v, (dict, list)):
                        recurse_json(v)
                    elif isinstance(v, str) and "http" in v:
                        add_url(v)
            elif isinstance(node, list):
                for item in node:
                    recurse_json(item)

        recurse_json(data)
    except Exception:
        pass

    # 2. 正則表達式抓取
    patterns = [
        r'''["']?(?:host|site|siteUrl|baseUrl|url|searchUrl|findRule|detailUrl|header_url|API|HOST|SITE|URL)["']?\s*[:=]\s*['"](https?://[^'"]+)['"]''',
        r'''['"](https?://(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}(?::\d+)?(?:/[^\s'"]*)?)['"]'''
    ]

    for pat in patterns:
        for u in re.findall(pat, code, re.IGNORECASE):
            add_url(u)

    return unique_urls


def test_url_alive(url: str) -> tuple[bool, str]:
    try:
        parsed = urlparse(url)
        headers = dict(BROWSER_HEADERS)
        if parsed.netloc:
            headers["Host"] = parsed.netloc
            headers["Referer"] = f"{parsed.scheme}://{parsed.netloc}/"

        try:
            resp = GLOBAL_SESSION.head(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, verify=False)
            if resp.status_code == 405:
                resp = GLOBAL_SESSION.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, verify=False, stream=True)
        except requests.RequestException:
            resp = GLOBAL_SESSION.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, verify=False, stream=True)

        if resp.status_code < 400 or resp.status_code in {401, 403, 405, 502, 503}:
            return True, f"HTTP {resp.status_code}"
        return False, f"HTTP {resp.status_code}"

    except requests.exceptions.SSLError:
        return True, "SSL 握手異常 (站點存活)"
    except requests.exceptions.ConnectionError as e:
        err_msg = str(e).lower()
        if any(k in err_msg for k in ["reset", "disconnected", "abort", "handshake"]):
            return True, "WAF 阻斷 (站點存活)"
        return False, "連線拒絕/超時"
    except Exception as e:
        return False, str(e)[:30]


def check_spider_file(file_info: tuple) -> dict:
    file_type, rel_path, full_path = file_info
    path_obj = Path(full_path)
    ext = path_obj.suffix.lower().replace(".", "")
    stem = path_obj.stem
    filename = path_obj.name

    start_time = datetime.now()
    result = {
        "type": file_type,
        "ext": ext,
        "name": stem,
        "file": rel_path.replace("\\", "/"),
        "full_path": str(full_path),
        "status": "❌ 失效",
        "detail": "未知錯誤",
        "latency_ms": 99999,
        "is_adult": False,
        "target_url": ""
    }

    try:
        code = path_obj.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        result["detail"] = f"無法讀取: {str(e)[:25]}"
        return result

    candidate_urls = extract_urls(code)

    # 1. 白名單優先
    if any(wl.lower() in stem.lower() for wl in WHITELIST_SPIDERS):
        target = candidate_urls[0] if candidate_urls else "https://unknown.site"
        result.update({
            "status": "✅ 正常",
            "detail": f"白名單強制保留 ({target})",
            "latency_ms": 100,
            "target_url": target,
            "is_adult": is_adult_content(filename, code, target)
        })
        return result

    # 2. Python 腳本動態反射分析
    if file_type == "Python":
        mod_name = f"dynamic_spider_{stem}_{abs(hash(str(full_path)))}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, full_path)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[mod_name] = module
                try:
                    spec.loader.exec_module(module)
                    for var_name in ["HOST", "host", "SITE", "site", "URL", "url", "WEB_SITE"]:
                        val = getattr(module, var_name, None)
                        if isinstance(val, str) and val.startswith("http"):
                            norm = normalize_url(val)
                            if norm and norm not in candidate_urls:
                                candidate_urls.insert(0, norm)

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
                        if getattr(spider, "host", None):
                            norm = normalize_url(spider.host)
                            if norm and norm not in candidate_urls:
                                candidate_urls.insert(0, norm)
                finally:
                    sys.modules.pop(mod_name, None)
        except Exception:
            pass

    # 3. 連線測活
    if candidate_urls:
        alive_info = None
        for raw_target in candidate_urls:
            ping_url = clean_test_url(raw_target)
            alive, msg = test_url_alive(ping_url)
            cost = int((datetime.now() - start_time).total_seconds() * 1000)
            if alive:
                alive_info = (raw_target, msg, cost)
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
    """
    精確移動至檔案所在資料夾底下的 NG 資料夾
    例：js/s/996影视.json -> js/s/NG/996影视.json
    """
    src = Path(full_path)
    ng_dir = src.parent / "NG"
    ng_dir.mkdir(parents=True, exist_ok=True)
    target = ng_dir / src.name
    shutil.move(str(src), str(target))
    return str(target.relative_to(BASE_DIR)).replace("\\", "/")


def deduplicate_sites(items: list[dict]) -> list[dict]:
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


def generate_tvbox_json(items: list, output_filepath: Path, spider_type: str = "py"):
    spider_jar = "./custom_spider.jar;md5;auto" if spider_type == "py" else "./drpy.min.js;md5;auto"

    sites = [
        {
            "key": f"{item['ext']}_{item['name']}",
            "name": f"[{item['ext'].upper()}] {item['name']} ({item['latency_ms']}ms)",
            "type": 3,
            "api": f"./{item['file']}",
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 1,
            "ext": item["target_url"]
        }
        for item in items
    ]

    config_data = {
        "spider": spider_jar,
        "sites": sites
    }

    output_filepath.write_text(json.dumps(config_data, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    requests.packages.urllib3.disable_warnings()

    target_files = []

    # 1. 遞迴搜尋 PY 目錄（避開各層級的 NG 資料夾）
    if PY_DIR.exists():
        for root, dirs, files in os.walk(PY_DIR):
            if "NG" in dirs:
                dirs.remove("NG")
            for f in files:
                if f.endswith(".py") and not f.startswith("__"):
                    full = Path(root) / f
                    target_files.append(("Python", str(full.relative_to(BASE_DIR)), str(full)))

    # 2. 遞迴搜尋 JS 目錄（包含 js/s, js/ss 等所有子目錄，掃描 .js 與 .json，避開各層級 NG）
    if JS_DIR.exists():
        for root, dirs, files in os.walk(JS_DIR):
            if "NG" in dirs:
                dirs.remove("NG")
            for f in files:
                if f in ["box_js.json", "fun_js.json", "box_py.json", "fun_py.json"]:
                    continue
                if f.endswith(".js") or f.endswith(".json"):
                    full = Path(root) / f
                    target_files.append(("JS", str(full.relative_to(BASE_DIR)), str(full)))

    if not target_files:
        print("未找到任何待測腳本。")
        return

    print(f"共發現 {len(target_files)} 個待測檔案 (含 JS/JSON)，開始檢測...")
    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(check_spider_file, item): item for item in target_files}
        for future in as_completed(future_map):
            r = future.result()
            results.append(r)
            print(f"[{r['type']}][{r['status']}] {r['file']} ({r['latency_ms']}ms) -> {r['detail']}")

    # 隔離失效檔案：移入該檔案所在同層目錄下的 NG 資料夾
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

    valid_results.sort(key=lambda x: x["latency_ms"])

    # 匯出 Python 配置
    py_valid = [r for r in valid_results if r["type"] == "Python"]
    box_py_items = deduplicate_sites([r for r in py_valid if not r["is_adult"]])
    fun_py_items = deduplicate_sites([r for r in py_valid if r["is_adult"]])
    generate_tvbox_json(box_py_items, BOX_PY_FILE, spider_type="py")
    generate_tvbox_json(fun_py_items, FUN_PY_FILE, spider_type="py")

    # 匯出 JS/JSON 配置 (涵蓋 js/, js/s/, js/ss/)
    js_valid = [r for r in valid_results if r["type"] == "JS"]
    box_js_items = deduplicate_sites([r for r in js_valid if not r["is_adult"]])
    fun_js_items = deduplicate_sites([r for r in js_valid if r["is_adult"]])
    generate_tvbox_json(box_js_items, BOX_JS_FILE, spider_type="js")
    generate_tvbox_json(fun_js_items, FUN_JS_FILE, spider_type="js")

    print("\n" + "=" * 50)
    print(f"✅ Python 一般類：{BOX_PY_FILE.name} (可用: {len(box_py_items)})")
    print(f"🔞 Python 成人類：{FUN_PY_FILE.name} (可用: {len(fun_py_items)})")
    print(f"✅ JS/JSON 一般類：{BOX_JS_FILE.name} (可用: {len(box_js_items)})")
    print(f"🔞 JS/JSON 成人類：{FUN_JS_FILE.name} (可用: {len(fun_js_items)})")
    print(f"📁 總計失效已隔離檔案：{moved_count} 個")
    print("=" * 50 + "\n")

    # 生成 Markdown 狀態報告
    results.sort(key=lambda x: (x["type"], x["status"], x["latency_ms"]))
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    md = [
        "# 🕷️ 影音網站爬蟲有效性檢測與配置生成報告\n",
        f"> **檢測時間**：`{now_str}`  \n",
        f"> **總檢測站點**：{len(results)} ｜ ✅ 有效可用：**{len(valid_results)}** ｜ ❌ 已隔離至各層 NG：**{moved_count}**\n",
        "### 📦 設定檔匯總\n",
        f"- 📺 **Python 一般類**：[`box_py.json`](./box_py.json) (共 **{len(box_py_items)}** 筆)",
        f"- 🔞 **Python 成人類**：[`fun_py.json`](./fun_py.json) (共 **{len(fun_py_items)}** 筆)",
        f"- 📺 **JS/JSON 一般類**：[`box_js.json`](./box_js.json) (共 **{len(box_js_items)}** 筆)",
        f"- 🔞 **JS/JSON 成人類**：[`fun_js.json`](./fun_js.json) (共 **{len(fun_js_items)}** 筆)\n",
        "### 📝 詳細檢測結果\n",
        "| 類型 | 副檔 | 名稱 / 相對路徑 | 狀態 | 耗時 (ms) | 分類 | 檢測資訊 |",
        "| :---: | :---: | :--- | :---: | :---: | :---: | :--- |"
    ]

    for r in results:
        cat_badge = "🔞 成人" if r["is_adult"] else "🎬 一般"
        md.append(f"| {r['type']} | `{r['ext']}` | `{r['file']}` | {r['status']} | {r['latency_ms']} | {cat_badge} | {r['detail']} |")

    REPORT_FILE.write_text("\n".join(md), encoding="utf-8")
    print(f"報告已更新至 {REPORT_FILE}")


if __name__ == "__main__":
    main()

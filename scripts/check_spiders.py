import os
import sys
import re
import shutil
import importlib.util
import inspect
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY_DIR = os.path.join(BASE_DIR, "py")
JS_DIR = os.path.join(BASE_DIR, "js")
REPORT_FILE = os.path.join(BASE_DIR, "SPIDER_STATUS.md")
TIMEOUT = 12
MAX_WORKERS = 10

# 將 py 相關目錄加入模組搜尋路徑，避免 import base.spider 失敗
for p in [BASE_DIR, PY_DIR, os.path.join(PY_DIR, "base")]:
    if os.path.exists(p) and p not in sys.path:
        sys.path.insert(0, p)

# 模擬現代瀏覽器的 Headers
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

def extract_urls(code: str) -> list:
    """提取程式碼內的所有可能影音站點 URL"""
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
    """測試網站連線狀態，防爬牆狀態（403/503）視為存活"""
    try:
        headers = dict(BROWSER_HEADERS)
        headers["Referer"] = url + "/"
        
        # 優先嘗試 GET 請求獲取主頁
        resp = requests.get(url, headers=headers, timeout=TIMEOUT, allow_redirects=True, verify=False)
        
        if resp.status_code < 400:
            return True, f"HTTP {resp.status_code}"
        elif resp.status_code in [403, 503]:
            # 遇到 Cloudflare 或防火牆阻擋，但表示伺服器與域名完全存活
            return True, f"HTTP {resp.status_code} (防爬阻擋，站點存活)"
        else:
            return False, f"HTTP {resp.status_code}"
    except requests.exceptions.SSLError:
        # SSL 證書失效但主機仍在
        return True, "SSL 驗證失敗 (站點存活)"
    except Exception as e:
        return False, str(e)[:35]

def check_spider_file(file_info: tuple) -> dict:
    file_type, rel_path, full_path = file_info
    start_time = datetime.now()
    result = {
        "type": file_type,
        "file": rel_path,
        "full_path": full_path,
        "status": "❌ 異常",
        "detail": "未知錯誤",
        "latency_ms": 0,
        "moved": False
    }

    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception as e:
        result["detail"] = f"無法讀取: {str(e)[:30]}"
        return result

    # 1. 若為 Python 腳本，優先嘗試載入與執行爬蟲核心介面
    if file_type == "Python":
        filename = os.path.basename(full_path)
        mod_name = f"mod_{os.path.splitext(filename)[0]}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, full_path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)

            spider = None
            for attr in dir(module):
                obj = getattr(module, attr)
                if inspect.isclass(obj) and obj.__module__ == module.__name__:
                    if "Spider" in attr or hasattr(obj, "homeContent"):
                        spider = obj()
                        break

            if spider:
                if hasattr(spider, "init"):
                    try: spider.init()
                    except Exception: pass
                
                # 測試 homeContent
                if hasattr(spider, "homeContent"):
                    res = spider.homeContent(True)
                    if res and isinstance(res, (dict, list, str)):
                        cost = int((datetime.now() - start_time).total_seconds() * 1000)
                        return {**result, "status": "✅ 正常", "detail": "homeContent 響應成功", "latency_ms": cost}
        except Exception:
            pass

    # 2. 備援策略：靜態抽取所有候選 URL 進行連線測試
    urls = extract_urls(code)
    if urls:
        alive_info = None
        for target_url in urls:
            alive, msg = test_url_alive(target_url)
            cost = int((datetime.now() - start_time).total_seconds() * 1000)
            if alive:
                alive_info = (target_url, msg, cost)
                break  # 只要其中一個主要網址活著就算通過

        if alive_info:
            target_url, msg, cost = alive_info
            # 存活即認定為可用，避免誤殺移到 NG
            result["status"] = "✅ 正常" if "HTTP 200" in msg else "⚠️ 站點存活(載入受限)"
            result["detail"] = f"{target_url} ({msg})"
            result["latency_ms"] = cost
        else:
            result["status"] = "❌ 失效"
            result["detail"] = f"所有候選網址連線失敗 (共測試 {len(urls)} 個)"
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
    return os.path.relpath(target_dest, BASE_DIR)

def main():
    # 關閉 SSL 不安全連線警告
    requests.packages.urllib3.disable_warnings()

    target_files = []

    # 掃描 py
    if os.path.exists(PY_DIR):
        for root, dirs, files in os.walk(PY_DIR):
            if "NG" in dirs:
                dirs.remove("NG")
            for f in files:
                if f.endswith(".py") and not f.startswith("__"):
                    full = os.path.join(root, f)
                    target_files.append(("Python", os.path.relpath(full, BASE_DIR), full))

    # 掃描 js
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
            print(f"[{r['type']}][{r['status']}] {r['file']} -> {r['detail']}")

    # 僅針對確定的 ❌ 執行移動（⚠️ 存活的不予移動）
    moved_count = 0
    for r in results:
        if "❌" in r["status"]:
            try:
                new_rel = move_to_ng(r["full_path"])
                r["detail"] += f" ➔ 已移至 `{new_rel}`"
                r["moved"] = True
                moved_count += 1
            except Exception as e:
                r["detail"] += f" (移動失敗: {str(e)[:20]})"

    results.sort(key=lambda x: (x["type"], x["status"], x["file"]))

    def calc_stats(sub_list):
        total = len(sub_list)
        ok = sum(1 for r in sub_list if "✅" in r["status"])
        warn = sum(1 for r in sub_list if "⚠️" in r["status"])
        fail = sum(1 for r in sub_list if "❌" in r["status"])
        rate = round(((ok + warn) / total * 100), 2) if total > 0 else 0
        return total, ok, warn, fail, rate

    tot_all, ok_all, warn_all, fail_all, rate_all = calc_stats(results)
    py_stats = calc_stats([r for r in results if r["type"] == "Python"])
    js_stats = calc_stats([r for r in results if r["type"] == "JS"])

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    md = [
        "# 🕷️ 影音網站爬蟲有效性檢測與歸檔報告\n",
        f"> **檢測時間**：`{now_str}`  \n",
        f"> **總體概況**：檢測 **{tot_all}** 個檔案 ｜ ✅ 正常：**{ok_all}** ｜ ⚠️ 警告(存活)：**{warn_all}** ｜ ❌ 失效已隔離：**{fail_all}** ｜ **可用率：{rate_all}%**\n",
        "### 📊 分類統計\n",
        f"- **Python (`py/`)**：共 **{py_stats[0]}** 個 ｜ 可用 **{py_stats[1] + py_stats[2]}** ｜ 失效已移至 NG **{py_stats[3]}** ｜ 可用率 **{py_stats[4]}%**",
        f"- **JavaScript (`js/`)**：共 **{js_stats[0]}** 個 ｜ 可用 **{js_stats[1] + js_stats[2]}** ｜ 失效已移至 NG **{js_stats[3]}** ｜ 可用率 **{js_stats[4]}%**\n",
        "### 📝 詳細檢測結果\n",
        "| 類型 | 原檔案路徑 | 狀態 | 耗時 (ms) | 檢測與處理資訊 |",
        "| :---: | :--- | :---: | :---: | :--- |"
    ]

    for r in results:
        md.append(f"| {r['type']} | `{r['file']}` | {r['status']} | {r['latency_ms']} | {r['detail']} |")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    print(f"\n檢測結束！共隔離移動了 {moved_count} 個失效腳本，報告已更新至 {REPORT_FILE}")

if __name__ == "__main__":
    main()

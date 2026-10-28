import os
import sys
import re
import importlib.util
import inspect
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

PY_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "py")
REPORT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "SPIDER_STATUS.md")
TIMEOUT = 10
MAX_WORKERS = 8

def extract_host_from_code(code: str) -> str:
    """備用方法：從原始碼中尋找可能的根網址"""
    patterns = [
        r'''(?:siteUrl|host|baseUrl|url)\s*=\s*['"](https?://[^'"]+)['"]''',
        r'''['"](https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})['"]'''
    ]
    for pattern in patterns:
        matches = re.findall(pattern, code)
        for url in matches:
            if not any(skip in url for skip in ["github", "googlevideo", "w3.org", "schema.org"]):
                return url
    return ""

def test_url_alive(url: str) -> tuple[bool, str]:
    """測試網址連線是否正常"""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        resp = requests.head(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code >= 400:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True)
        if resp.status_code < 400:
            return True, f"HTTP {resp.status_code}"
        return False, f"HTTP {resp.status_code}"
    except Exception as e:
        return False, str(e)[:40]

def check_single_spider(py_path: str) -> dict:
    filename = os.path.basename(py_path)
    result = {
        "file": filename,
        "name": filename.replace(".py", ""),
        "status": "❌ 異常",
        "detail": "未知錯誤",
        "latency_ms": 0
    }
    
    start_time = datetime.now()
    
    # 1. 嘗試動態載入模組
    try:
        spec = importlib.util.spec_from_file_location(filename[:-3], py_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[filename[:-3]] = module
        spec.loader.exec_module(module)
        
        spider_instance = None
        # 尋找繼承或命名的 Spider 類別
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if inspect.isclass(attr) and attr.__module__ == module.__name__:
                if "Spider" in attr_name or hasattr(attr, "homeContent"):
                    spider_instance = attr()
                    break
        
        # 嘗試執行介面方法檢驗數據
        if spider_instance:
            if hasattr(spider_instance, "init"):
                try:
                    spider_instance.init()
                except Exception:
                    pass
            
            # 優先測試首頁內容
            if hasattr(spider_instance, "homeContent"):
                home_res = spider_instance.homeContent(True)
                if home_res and isinstance(home_res, (dict, list, str)):
                    cost = int((datetime.now() - start_time).total_seconds() * 1000)
                    return {"file": filename, "name": spider_instance.getName() if hasattr(spider_instance, "getName") else filename, "status": "✅ 正常", "detail": "homeContent 響應成功", "latency_ms": cost}
            
            if hasattr(spider_instance, "homeVideoContent"):
                vod_res = spider_instance.homeVideoContent()
                if vod_res:
                    cost = int((datetime.now() - start_time).total_seconds() * 1000)
                    return {"file": filename, "name": filename, "status": "✅ 正常", "detail": "homeVideoContent 響應成功", "latency_ms": cost}

    except Exception as e:
        # 動態載入失敗，轉為靜態分析網址測試
        pass

    # 2. 備援策略：靜態擷取 Host 連線測試
    try:
        with open(py_path, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
        target_url = extract_host_from_code(code)
        
        if target_url:
            alive, msg = test_url_alive(target_url)
            cost = int((datetime.now() - start_time).total_seconds() * 1000)
            if alive:
                result["status"] = "⚠️ 站點存活(腳本載入受限)"
                result["detail"] = f"站點可連線 ({msg}): {target_url[:30]}"
            else:
                result["status"] = "❌ 失效"
                result["detail"] = f"連線失敗 ({msg})"
            result["latency_ms"] = cost
        else:
            result["detail"] = "無明確 host 且模組無法呼叫"
    except Exception as e:
        result["detail"] = str(e)[:40]
        
    return result

def main():
    if not os.path.exists(PY_DIR):
        print(f"Directory {PY_DIR} not found.")
        sys.exit(1)

    py_files = [os.path.join(PY_DIR, f) for f in os.listdir(PY_DIR) if f.endswith(".py") and not f.startswith("__")]
    
    print(f"找到 {len(py_files)} 個爬蟲腳本，開始並行檢測...")
    results = []
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {executor.submit(check_single_spider, path): path for path in py_files}
        for future in as_completed(future_map):
            res = future.result()
            results.append(res)
            print(f"[{res['status']}] {res['file']} - {res['detail']}")

    # 排序：依狀態與檔名
    results.sort(key=lambda x: (x["status"], x["file"]))
    
    # 統計數量
    total = len(results)
    success_count = sum(1 for r in results if "✅" in r["status"])
    warning_count = sum(1 for r in results if "⚠️" in r["status"])
    failed_count = sum(1 for r in results if "❌" in r["status"])
    success_rate = round(((success_count + warning_count) / total * 100), 2) if total > 0 else 0

    # 建立 Markdown 報告
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    md = []
    md.append("# 🕷️ 影音網站爬蟲有效性檢測報告\n")
    md.append(f"> **檢測時間**：`{now_str}`  \n")
    md.append(f"> **統計概況**：共檢測 **{total}** 個腳本 ｜ ✅ 正常：**{success_count}** ｜ ⚠️ 站點存活：**{warning_count}** ｜ ❌ 失效：**{failed_count}** ｜ 可用率：**{success_rate}%**\n")
    md.append("\n| 腳本名稱 | 檢測狀態 | 耗時 (ms) | 檢測資訊 |")
    md.append("| :--- | :---: | :---: | :--- |")
    
    for r in results:
        md.append(f"| `{r['file']}` | {r['status']} | {r['latency_ms']} | {r['detail']} |")

    content = "\n".join(md)
    
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"\n報告已產生至 {REPORT_FILE}")

if __name__ == "__main__":
    main()

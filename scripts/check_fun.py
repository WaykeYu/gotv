import os
import re
import json
import time
import random
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

# 優先嘗試載入 curl_cffi 以繞過 Cloudflare TLS 指紋檢測；若無安裝則自動切換為 requests
try:
    from curl_cffi import requests as web_client
    USE_CURL_CFFI = True
except ImportError:
    import requests as web_client
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    USE_CURL_CFFI = False

# ==================== 設定區塊 ====================
TARGET_FILE = "fun1.json"
NG_DIR = "collect/NG"
STATUS_FILE = "fun_STATUS.md"

TIMEOUT = 12       # 請求逾時秒數 (秒)
MAX_WORKERS = 10   # 平行檢測線程數
MAX_RETRIES = 2    # 單站最大重試次數

# 現代瀏覽器完整特徵標頭 (含 Client Hints 與 Sec-Fetch 序列)
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/json",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive"
}

tz_tw = timezone(timedelta(hours=8))

# ==================== 輔助工具函數 ====================

def write_status_and_summary(content: str):
    """將報告同步寫入 fun_STATUS.md 與 GitHub Actions Summary"""
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(content)

def clean_json_content(raw: str) -> str:
    """清理 TVBox 常見非標準 JSON 語法 (NBSP、全形空格、註解、尾隨逗號、兩物件間漏逗號)"""
    text = (
        raw.replace("\u00a0", " ")
        .replace("\u3000", " ")
        .replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\r\n", "\n")
    )
    # 移除多行註解 /* ... */ 與單行註解 // ...
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'(?<!:)\/\/.*$', '', text, flags=re.MULTILINE)

    # 自動修復：物件或陣列之間缺少逗號 (例如 '} \n {' 自動修正為 '}, \n {')
    text = re.sub(r'([}\]])\s*\n\s*([{\[])', r'\1,\n\2', text)

    # 移除末尾多餘的逗號
    text = re.sub(r',\s*([\]}])', r'\1', text)
    return text.strip()

def extract_target_url(item):
    """自適應提取各類 TVBox 格式下的 URL，特別適配 type:3 的 ext 遠端伺服器"""
    if isinstance(item, str):
        return item.strip(), item.strip()

    if isinstance(item, dict):
        name = item.get("name") or item.get("title") or item.get("key") or "未知"
        
        # 1. 優先判定 ext 是否為遠端 HTTP 網址 (專為 type:3 / Python 爬蟲設計)
        ext = str(item.get("ext", "")).strip()
        if ext.startswith(("http://", "https://")):
            return ext, str(name).strip()

        # 2. 依序檢查 url, link, api
        for field in ["url", "link", "api"]:
            val = str(item.get(field, "")).strip()
            if val.startswith(("http://", "https://")):
                return val, str(name).strip()

        # 3. 本地爬蟲備援
        fallback_val = item.get("api") or item.get("url") or ""
        return str(fallback_val).strip(), str(name).strip()

    return "", "未知"

def build_probe_url(url: str) -> str:
    """構造 MacCMS 採集源 API 測試路徑：帶入 ac=list 獲取帶有 code:1 的回應"""
    clean_url = url.strip()
    if "api.php/provide/vod" in clean_url:
        base = clean_url.rstrip("/")
        sep = "&" if "?" in base else "?"
        if "ac=" not in base:
            return f"{base}{sep}ac=list&pagesize=1"
        return base
    return clean_url

# ==================== 連線檢測核心 ====================

def test_url_latency(item):
    """
    連線檢測函數：
    1. 最優先判定：只要回應中出現 "code":1 或 JSON code 為 1，直接判定有效。
    2. 次級判定：標準 HTTP < 400 放行。
    3. 特殊判定：HTTP 403 (Cloudflare 防火牆攔截但站點在線) 判定存活放行。
    """
    url, name = extract_target_url(item)

    if not url or not url.startswith(("http://", "https://")):
        return {
            "valid": False, "item": item, "name": name, "url": str(url),
            "latency": 99999, "error": f"非有效網址格式 [{url[:25]}]"
        }

    probe_url = build_probe_url(url)

    for attempt in range(MAX_RETRIES):
        start_time = time.perf_counter()
        try:
            if USE_CURL_CFFI:
                resp = web_client.get(
                    probe_url,
                    headers=BROWSER_HEADERS,
                    impersonate="chrome124",
                    timeout=TIMEOUT,
                    verify=False,
                    allow_redirects=True
                )
            else:
                resp = web_client.get(
                    probe_url,
                    headers=BROWSER_HEADERS,
                    timeout=TIMEOUT,
                    verify=False,
                    allow_redirects=True
                )

            elapsed = round((time.perf_counter() - start_time) * 1000, 1)
            body_sample = resp.text[:4000] if resp.text else ""

            # ---------------- 判定條件 1 (最優先)：出現 code:1 一律判定有效 ----------------
            has_code_1 = ('"code":1' in body_sample) or ('"code": 1' in body_sample)
            if not has_code_1 and body_sample.startswith(("{", "[")):
                try:
                    data = resp.json()
                    if isinstance(data, dict) and data.get("code") in (1, "1"):
                        has_code_1 = True
                except Exception:
                    pass

            if has_code_1:
                return {
                    "valid": True, "item": item, "name": name, "url": url,
                    "latency": elapsed, "status_code": "code:1 (成功)"
                }

            # ---------------- 判定條件 2：標準 HTTP 狀態碼 < 400 ----------------
            if resp.status_code < 400:
                return {
                    "valid": True, "item": item, "name": name, "url": url,
                    "latency": elapsed, "status_code": resp.status_code
                }

            # ---------------- 判定條件 3：Cloudflare 403 防護放行 ----------------
            # 機房 IP 被擋但站點在線，判定為有效存活
            if resp.status_code == 403:
                is_cf = "cf-ray" in resp.headers or "cloudflare" in resp.headers.get("server", "").lower()
                status_tag = "403 (CF在線放行)" if is_cf else "403 (防護放行)"
                return {
                    "valid": True, "item": item, "name": name, "url": url,
                    "latency": elapsed, "status_code": status_tag
                }

            # 遭遇 429 或 503 時進行退避重試
            if resp.status_code in (429, 503) and attempt < MAX_RETRIES - 1:
                backoff_time = (1.5 * (attempt + 1)) + random.uniform(0.3, 0.7)
                time.sleep(backoff_time)
                continue

            if attempt == MAX_RETRIES - 1:
                return {
                    "valid": False, "item": item, "name": name, "url": url,
                    "latency": 99999, "error": f"HTTP {resp.status_code}"
                }

        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                err_type = type(e).__name__
                if "Timeout" in err_type:
                    err_msg = "連線逾時 (Timeout)"
                elif "SSL" in err_type:
                    err_msg = "SSL憑證錯誤"
                elif "Connection" in err_type:
                    err_msg = "連線中斷"
                else:
                    err_msg = f"例外: {err_type}"

                return {
                    "valid": False, "item": item, "name": name, "url": url,
                    "latency": 99999, "error": err_msg
                }

            time.sleep(1.0 + random.uniform(0.2, 0.5))

    return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": "未知異常"}

# ==================== 統計報表生成 ====================

def generate_status_markdown(target_file, engine_tag, valid_results, invalid_results, duplicate_count, check_time_str, ng_filename):
    """產生結構化、視覺化燈號標記的 Markdown 統計表格"""
    total = len(valid_results) + len(invalid_results)
    ok_count = len(valid_results)
    ng_count = len(invalid_results)
    survival_rate = (ok_count / total * 100) if total > 0 else 0
    avg_latency = round(sum(r["latency"] for r in valid_results) / ok_count, 1) if ok_count > 0 else 0

    speed_fast = sum(1 for r in valid_results if r["latency"] < 300)
    speed_normal = sum(1 for r in valid_results if 300 <= r["latency"] < 600)
    speed_slow = sum(1 for r in valid_results if 600 <= r["latency"] < 1000)
    speed_bad = sum(1 for r in valid_results if r["latency"] >= 1000)
    code1_count = sum(1 for r in valid_results if "code:1" in str(r.get("status_code", "")))

    pct_fast = round(speed_fast / ok_count * 100, 1) if ok_count else 0
    pct_normal = round(speed_normal / ok_count * 100, 1) if ok_count else 0
    pct_slow = round(speed_slow / ok_count * 100, 1) if ok_count else 0
    pct_bad = round(speed_bad / ok_count * 100, 1) if ok_count else 0

    md = f"""# 📊 {target_file} 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`{check_time_str}`  
> 🛠️ **檢測核心**：`{engine_tag}` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **{code1_count}** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **{total}** | **{ok_count}** | **{ng_count}** | **{code1_count}** | **{duplicate_count}** | `{survival_rate:.1f}%` | **{avg_latency} ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**{speed_fast}** 站 ({pct_fast}%)
- 🟡 **良好** (`300 ~ 600ms`)：**{speed_normal}** 站 ({pct_normal}%)
- 🟠 **普通** (`600 ~ 1000ms`)：**{speed_slow}** 站 ({pct_slow}%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**{speed_bad}** 站 ({pct_bad}%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
"""

    for idx, r in enumerate(valid_results, 1):
        lat = r["latency"]
        if lat < 300:
            badge = "🟢 極速"
        elif lat < 600:
            badge = "🟡 良好"
        elif lat < 1000:
            badge = "🟠 普通"
        else:
            badge = "🔴 遲鈍"

        clean_url = r['url'][:55] + "..." if len(r['url']) > 55 else r['url']
        md += f"| {idx} | `{r['name']}` | **{lat}** | {badge} | `{r.get('status_code', 200)}` | `{clean_url}` |\n"

    if invalid_results:
        md += f"""
---

### ⚠️ 本次移入 NG 項目 (共 {ng_count} 筆)
> 📦 **封存檔案**：`{ng_filename}`

| 站點名稱 | 移入原因 | 網址預覽 |
| :--- | :--- | :--- |
"""
        for r in invalid_results:
            clean_url = r['url'][:60] + "..." if len(r['url']) > 60 else r['url']
            md += f"| `{r['name']}` | `{r.get('error', 'Error')}` | `{clean_url}` |\n"

    return md

# ==================== 主流程控制 ====================

def check_and_sort():
    check_time_str = datetime.now(tz_tw).strftime("%Y-%m-%d %H:%M:%S")

    # 1. 檢查檔案存在
    if not os.path.exists(TARGET_FILE):
        err = f"# ❌ 檢測失敗\n\n- **時間**：`{check_time_str}`\n- **原因**：找不到 `{TARGET_FILE}`。"
        print(err)
        write_status_and_summary(err)
        return

    # 2. 讀取並清洗 JSON (包含正則自動補逗號與出錯上下文定位)
    try:
        with open(TARGET_FILE, "r", encoding="utf-8") as f:
            raw_text = f.read()

        cleaned_text = clean_json_content(raw_text)
        data = json.loads(cleaned_text)
    except Exception as e:
        lines = raw_text.splitlines()
        match = re.search(r'line (\d+)', str(e))
        snippet = ""
        if match:
            err_line = int(match.group(1))
            start = max(0, err_line - 4)
            end = min(len(lines), err_line + 3)
            snippet = "\n".join([f"{i+1}: {lines[i]}" for i in range(start, end)])

        err = f"# ❌ 檢測失敗\n\n- **時間**：`{check_time_str}`\n- **原因**：JSON 解析失敗: `{e}`\n\n```json\n{snippet}\n```"
        print(err)
        write_status_and_summary(err)
        return

    os.makedirs(NG_DIR, exist_ok=True)

    # 3. 識別清單欄位
    target_key = None
    items = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ["urls", "channels", "lives", "sites"]:
            if key in data and isinstance(data[key], list) and len(data[key]) > 0:
                target_key = key
                items = data[key]
                break

    if not items:
        available_keys = list(data.keys()) if isinstance(data, dict) else "非字典格式"
        err = f"# ⚠️ 檢測跳過\n\n- **時間**：`{check_time_str}`\n- **原因**：未在 `{TARGET_FILE}` 找到包含網址的陣列欄位。\n- **目前欄位**：`{available_keys}`"
        print(err)
        write_status_and_summary(err)
        return

    engine_tag = "curl_cffi (JA3偽裝)" if USE_CURL_CFFI else "標準 requests"
    total_original = len(items)

    # ==================== 網址去重機制 ====================
    seen_urls = {}
    unique_items = []
    duplicate_results = []

    for item in items:
        url, name = extract_target_url(item)
        if url.startswith(("http://", "https://")):
            if url in seen_urls:
                duplicate_results.append({
                    "valid": False,
                    "item": item,
                    "name": name,
                    "url": url,
                    "latency": 0,
                    "error": f"重複網址 (首見於: {seen_urls[url]})"
                })
            else:
                seen_urls[url] = name
                unique_items.append(item)
        else:
            unique_items.append(item)

    duplicate_count = len(duplicate_results)
    print(f"[{check_time_str}] 使用引擎 [{engine_tag}]，命中欄位 [{target_key or 'ROOT_LIST'}]")
    print(f"總項目: {total_original} 筆 | 去除重複: {duplicate_count} 筆 | 待測獨立項目: {len(unique_items)} 筆")

    # 4. 多線程連線檢測
    tested_results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(test_url_latency, item) for item in unique_items]
        for future in as_completed(futures):
            res = future.result()
            tested_results.append(res)
            status_tag = "OK" if res["valid"] else "NG"
            print(f"[{status_tag}] {res['name']} -> {res.get('status_code', res.get('error'))} ({res['latency']}ms)")

    valid_results = [r for r in tested_results if r["valid"]]
    invalid_results = [r for r in tested_results if not r["valid"]] + duplicate_results

    # 5. 排序：依響應時間由快到慢排序
    valid_results.sort(key=lambda x: x["latency"])

    # 6. 回存有效項目至原設定檔
    if target_key:
        data[target_key] = [r["item"] for r in valid_results]
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif isinstance(data, list):
        data = [r["item"] for r in valid_results]
        with open(TARGET_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # 7. 保留原始段落並附加原因，寫入 collect/NG/
    ng_filename = ""
    if invalid_results:
        prefix = os.path.splitext(os.path.basename(TARGET_FILE))[0]
        ng_filename = f"{NG_DIR}/{prefix}_ng_{datetime.now(tz_tw).strftime('%Y%m%d_%H%M%S')}.json"
        ng_data = []

        for r in invalid_results:
            raw_item = r["item"]

            if isinstance(raw_item, dict):
                augmented_item = deepcopy(raw_item)
                augmented_item["_error_reason"] = r.get("error", "檢測失敗")
                augmented_item["_tested_url"] = r.get("url", "")
                augmented_item["_fail_latency"] = r.get("latency", 99999)
                augmented_item["_checked_at"] = check_time_str
                ng_data.append(augmented_item)
            else:
                ng_data.append({
                    "original_item": raw_item,
                    "_error_reason": r.get("error", "檢測失敗"),
                    "_tested_url": r.get("url", ""),
                    "_checked_at": check_time_str
                })

        with open(ng_filename, "w", encoding="utf-8") as f:
            json.dump(ng_data, f, ensure_ascii=False, indent=2)

    # 8. 產出 Markdown 統計報表
    md_report = generate_status_markdown(
        target_file=TARGET_FILE,
        engine_tag=engine_tag,
        valid_results=valid_results,
        invalid_results=invalid_results,
        duplicate_count=duplicate_count,
        check_time_str=check_time_str,
        ng_filename=ng_filename
    )
    write_status_and_summary(md_report)

    ok_count = len(valid_results)
    ng_count = len(invalid_results)
    failed_conn_count = ng_count - duplicate_count
    print(f"檢測完成！存活: {ok_count}, 重複: {duplicate_count}, 連線失敗: {failed_conn_count}，已回存 {TARGET_FILE} 與 {STATUS_FILE}")

if __name__ == "__main__":
    check_and_sort()

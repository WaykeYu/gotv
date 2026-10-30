import os
import re
import json
import time
import requests
import urllib3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

# 關閉 SSL 不安全警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOX_FILE = "box1.json"
NG_DIR = "collect/NG"
STATUS_FILE = "box_STATUS.md"

TIMEOUT = 12       # 提高至 12 秒，給跨國連線充足緩衝
MAX_WORKERS = 8     # 降至 8，避免被站點 WAF 限速觸發 403/逾時

# 完整高仿真瀏覽器標頭 (含 Sec-CH 與 Sec-Fetch，可大幅突破防禦)
BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,application/json,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "Connection": "keep-alive"
}

tz_tw = timezone(timedelta(hours=8))

def write_status_and_summary(content: str):
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(content)

    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(content)

def clean_json_content(raw: str) -> str:
    """清理 TVBox 常見非標準 JSON 語法 (NBSP、全形空格、註解、尾隨逗號)"""
    text = (
        raw.replace("\u00a0", " ")
        .replace("\u3000", " ")
        .replace("\ufeff", "")
        .replace("\u200b", "")
        .replace("\r\n", "\n")
    )
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    text = re.sub(r'(?<!:)\/\/.*$', '', text, flags=re.MULTILINE)
    text = re.sub(r',\s*([\]}])', r'\1', text)
    return text.strip()

def extract_target_url(item):
    if isinstance(item, str):
        return item.strip(), item.strip()
    if isinstance(item, dict):
        url = item.get("url") or item.get("link") or item.get("api") or ""
        name = item.get("name") or item.get("title") or item.get("key") or url
        return str(url).strip(), str(name).strip()
    return "", "未知"

def build_probe_url(url: str) -> str:
    """構造 MacCMS 測試路徑：帶入 ac=list 才能正確觸發 API 回應"""
    if "api.php/provide/vod" in url:
        sep = "&" if "?" in url else "?"
        if "ac=" not in url:
            return f"{url}{sep}ac=list&pagesize=1"
    return url

def is_maccms_alive_content(text: str) -> bool:
    """即使 HTTP 回傳 403/500，只要含有 CMS 特徵字眼，代表伺服器正常運作"""
    keywords = ["\"code\"", "\"msg\"", "mac_", "provide/vod", "\"list\":", "vod_name", "type_name"]
    return any(k in text for k in keywords)

def test_url_latency(item):
    url, name = extract_target_url(item)

    if not url or not url.startswith(("http://", "https://")):
        return {
            "valid": False, "item": item, "name": name, "url": str(url),
            "latency": 99999, "error": f"非有效網址格式 [{url[:25]}]"
        }

    probe_url = build_probe_url(url)
    
    # 進行兩次嘗試（防止網路瞬斷或冷啟動 Timeout）
    for attempt in range(2):
        start_time = time.perf_counter()
        try:
            # 建立獨立 session 模擬乾淨連線
            with requests.Session() as s:
                resp = s.get(
                    probe_url,
                    headers=BROWSER_HEADERS,
                    timeout=TIMEOUT,
                    verify=False,
                    allow_redirects=True
                )
                elapsed = round((time.perf_counter() - start_time) * 1000, 1)

                # 條件 1：標準狀態碼 < 400
                if resp.status_code < 400:
                    return {
                        "valid": True, "item": item, "name": name, "url": url,
                        "latency": elapsed, "status_code": resp.status_code
                    }

                # 條件 2：若遇到 403、503，檢查內文是否為有效的 CMS 回應
                body_sample = resp.text[:1000] if resp.text else ""
                if is_maccms_alive_content(body_sample):
                    return {
                        "valid": True, "item": item, "name": name, "url": url,
                        "latency": elapsed, "status_code": f"{resp.status_code}(放行)"
                    }

                # 若是最後一次嘗試依然失敗
                if attempt == 1:
                    return {
                        "valid": False, "item": item, "name": name, "url": url,
                        "latency": 99999, "error": f"HTTP {resp.status_code}"
                    }

        except requests.exceptions.Timeout:
            if attempt == 1:
                return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": "連線逾時 (Timeout)"}
            time.sleep(1)  # 遇超時等待 1 秒後重試第二次
        except requests.exceptions.SSLError:
            return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": "SSL憑證錯誤"}
        except requests.exceptions.ConnectionError as ce:
            if attempt == 1:
                return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": f"連線中斷 ({type(ce).__name__})"}
            time.sleep(1)
        except Exception as e:
            if attempt == 1:
                return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": f"例外: {type(e).__name__}"}
            time.sleep(1)

    return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": "未知異常"}

def check_and_sort():
    check_time_str = datetime.now(tz_tw).strftime("%Y-%m-%d %H:%M:%S")

    if not os.path.exists(BOX_FILE):
        err = f"# ❌ 檢測失敗\n\n- **時間**：`{check_time_str}`\n- **原因**：找不到 `{BOX_FILE}`。"
        print(err)
        write_status_and_summary(err)
        return

    try:
        with open(BOX_FILE, "r", encoding="utf-8") as f:
            raw_text = f.read()

        cleaned_text = clean_json_content(raw_text)
        data = json.loads(cleaned_text)
    except Exception as e:
        err = f"# ❌ 檢測失敗\n\n- **時間**：`{check_time_str}`\n- **原因**：JSON 解析失敗: `{e}`"
        print(err)
        write_status_and_summary(err)
        return

    os.makedirs(NG_DIR, exist_ok=True)

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
        err = f"# ⚠️ 檢測跳過\n\n- **時間**：`{check_time_str}`\n- **原因**：未在 `{BOX_FILE}` 找到包含網址的陣列欄位 (urls, channels, lives, sites)。\n- **目前欄位**：`{available_keys}`"
        print(err)
        write_status_and_summary(err)
        return

    print(f"[{check_time_str}] 命中欄位 [{target_key or 'ROOT_LIST'}]，共 {len(items)} 筆項目，開始檢測...")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(test_url_latency, item) for item in items]
        for future in as_completed(futures):
            res = future.result()
            results.append(res)
            status_tag = "OK" if res["valid"] else "NG"
            print(f"[{status_tag}] {res['name']} -> {res.get('status_code', res.get('error'))} ({res['latency']}ms)")

    valid_results = [r for r in results if r["valid"]]
    invalid_results = [r for r in results if not r["valid"]]

    valid_results.sort(key=lambda x: x["latency"])

    if target_key:
        data[target_key] = [r["item"] for r in valid_results]
        with open(BOX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif isinstance(data, list):
        data = [r["item"] for r in valid_results]
        with open(BOX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    ng_filename = ""
    if invalid_results:
        ng_filename = f"{NG_DIR}/ng_{datetime.now(tz_tw).strftime('%Y%m%d_%H%M%S')}.json"
        ng_data = [{
            "name": r["name"],
            "url": r["url"],
            "error": r.get("error", "Failed"),
            "checked_at": check_time_str
        } for r in invalid_results]
        with open(ng_filename, "w", encoding="utf-8") as f:
            json.dump(ng_data, f, ensure_ascii=False, indent=2)

    total = len(items)
    ok_count = len(valid_results)
    ng_count = len(invalid_results)
    survival_rate = (ok_count / total * 100) if total > 0 else 0
    avg_latency = round(sum(r["latency"] for r in valid_results) / ok_count, 1) if ok_count > 0 else 0

    md_content = f"""# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **最後更新時間 (UTC+8)**：`{check_time_str}`  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。

---

### 📈 綜合健康指標

| 總檢測數 | 存活數量 | 失效數量 (移至 NG) | 存活率 | 平均響應時間 |
| :---: | :---: | :---: | :---: | :---: |
| **{total}** | **{ok_count}** | **{ng_count}** | **{survival_rate:.2f}%** | **{avg_latency} ms** |

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| 排名 | 名稱 | 響應時間 (ms) | 狀態碼 | 網址預覽 |
| :---: | :--- | :---: | :---: | :--- |
"""
    for idx, r in enumerate(valid_results, 1):
        clean_url = r['url'][:55] + "..." if len(r['url']) > 55 else r['url']
        md_content += f"| {idx} | `{r['name']}` | **{r['latency']}** | `{r.get('status_code', 200)}` | `{clean_url}` |\n"

    if invalid_results:
        md_content += f"""
---

### ⚠️ 本次失效來源（已移出）
- **NG 封存檔**：`{ng_filename}`

| 名稱 | 錯誤原因 | 網址預覽 |
| :--- | :--- | :--- |
"""
        for r in invalid_results:
            clean_url = r['url'][:60] + "..." if len(r['url']) > 60 else r['url']
            md_content += f"| `{r['name']}` | `{r.get('error', 'Error')}` | `{clean_url}` |\n"

    write_status_and_summary(md_content)
    print(f"檢測完成！存活: {ok_count}, 失效: {ng_count}，已回存 {BOX_FILE} 與 {STATUS_FILE}")

if __name__ == "__main__":
    check_and_sort()

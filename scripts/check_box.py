import os
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

TIMEOUT = 8
MAX_WORKERS = 10
HEADERS = {
    "User-Agent": "okhttp/3.15.0; TVBox/1.0",
    "Accept": "*/*",
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

def extract_target_url(item):
    """提取 URL 與名稱，支援字典或純字串"""
    if isinstance(item, str):
        return item.strip(), item.strip()
    if isinstance(item, dict):
        url = item.get("url") or item.get("link") or item.get("api") or ""
        name = item.get("name") or item.get("title") or item.get("key") or url
        return str(url).strip(), str(name).strip()
    return "", "未知"

def test_url_latency(item):
    """使用 GET stream 方式測試連線與回應時間 (ms)"""
    url, name = extract_target_url(item)

    if not url or not url.startswith(("http://", "https://")):
        return {
            "valid": False, "item": item, "name": name, "url": str(url),
            "latency": 99999, "error": f"非有效網址 [{url[:20]}]"
        }

    start_time = time.perf_counter()
    try:
        resp = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            stream=True,
            verify=False,
            allow_redirects=True
        )
        elapsed = round((time.perf_counter() - start_time) * 1000, 1)

        if resp.status_code < 400:
            resp.close()
            return {
                "valid": True, "item": item, "name": name, "url": url,
                "latency": elapsed, "status_code": resp.status_code
            }
        else:
            resp.close()
            return {
                "valid": False, "item": item, "name": name, "url": url,
                "latency": 99999, "error": f"HTTP {resp.status_code}"
            }
    except requests.exceptions.Timeout:
        return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": "連線逾時"}
    except requests.exceptions.SSLError:
        return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": "SSL錯誤"}
    except requests.exceptions.ConnectionError as ce:
        return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": f"連線異常 ({type(ce).__name__})"}
    except Exception as e:
        return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": f"例外: {type(e).__name__}"}

def check_and_sort():
    check_time_str = datetime.now(tz_tw).strftime("%Y-%m-%d %H:%M:%S")

    if not os.path.exists(BOX_FILE):
        err = f"# ❌ 檢測失敗\n\n- **時間**：`{check_time_str}`\n- **原因**：找不到 `{BOX_FILE}`。"
        print(err)
        write_status_and_summary(err)
        return

    try:
        with open(BOX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        err = f"# ❌ 檢測失敗\n\n- **時間**：`{check_time_str}`\n- **原因**：JSON 解析失敗: `{e}`"
        print(err)
        write_status_and_summary(err)
        return

    os.makedirs(NG_DIR, exist_ok=True)

    # 識別 TVBox JSON 中的清單欄位
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
        err = f"# ⚠️ 檢測跳過\n\n- **時間**：`{check_time_str}`\n- **原因**：未在 `{BOX_FILE}` 找到包含網址的陣列欄位 (urls, channels, lives, sites)。"
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

    # 依響應速度由快到慢排序
    valid_results.sort(key=lambda x: x["latency"])

    # 回存至原本的 JSON 格式
    if target_key:
        data[target_key] = [r["item"] for r in valid_results]
        with open(BOX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    elif isinstance(data, list):
        data = [r["item"] for r in valid_results]
        with open(BOX_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # 將失效項目存至 collect/NG/
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

    # 建立 box_STATUS.md
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
    print(f"檢測完成！存活: {ok_count}, 失效: {ng_count}")

if __name__ == "__main__":
    check_and_sort()

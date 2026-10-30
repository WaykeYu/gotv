import os
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

BOX_FILE = "box1.json"
NG_DIR = "collect/NG"
STATUS_FILE = "box_STATUS.md"

TIMEOUT = 5  # 請求逾時秒數
MAX_WORKERS = 15  # 並行檢測線程數
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# 台灣時間 (UTC+8)
tz_tw = timezone(timedelta(hours=8))

def test_url_latency(item):
    """檢測 URL 連線並計算回應時間 (ms)"""
    url = item.get("url") if isinstance(item, dict) else item
    name = item.get("name", "未知") if isinstance(item, dict) else url

    if not url or not str(url).startswith(("http://", "https://")):
        return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": "Invalid URL Protocol"}

    start_time = time.perf_counter()
    try:
        resp = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code >= 400 and resp.status_code in [403, 405]:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=True)

        if resp.status_code < 400:
            elapsed = round((time.perf_counter() - start_time) * 1000, 1)
            return {"valid": True, "item": item, "name": name, "url": url, "latency": elapsed, "status_code": resp.status_code}
        else:
            return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"valid": False, "item": item, "name": name, "url": url, "latency": 99999, "error": type(e).__name__}

def check_and_sort():
    if not os.path.exists(BOX_FILE):
        print(f"錯誤：找不到 {BOX_FILE}")
        return

    with open(BOX_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"JSON 解析失敗: {e}")
            return

    os.makedirs(NG_DIR, exist_ok=True)

    # 相容常見欄位 (channels / urls / lives)
    target_key = "channels" if "channels" in data else ("urls" if "urls" in data else "lives")
    items = data.get(target_key, [])
    if not items:
        print("未在 JSON 中找到可檢測的清單欄位 (channels / urls / lives)")
        return

    check_time_str = datetime.now(tz_tw).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{check_time_str}] 開始檢測 (總筆數: {len(items)})...")

    results = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(test_url_latency, item) for item in items]
        for future in as_completed(futures):
            results.append(future.result())

    valid_results = [r for r in results if r["valid"]]
    invalid_results = [r for r in results if not r["valid"]]

    # 依回應時間由快到慢排序
    valid_results.sort(key=lambda x: x["latency"])

    # 更新過濾與排序後的資料並回存
    data[target_key] = [r["item"] for r in valid_results]
    with open(BOX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 失效項目移存至 NG 資料夾
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

    # 統計指標計算
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

| 名稱 | 錯誤類型 | 網址預覽 |
| :--- | :--- | :--- |
"""
        for r in invalid_results:
            clean_url = r['url'][:60] + "..." if len(r['url']) > 60 else r['url']
            md_content += f"| `{r['name']}` | `{r.get('error', 'Error')}` | `{clean_url}` |\n"

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"檢測完成：存活 {ok_count}/{total}，已寫入 {BOX_FILE} 與 {STATUS_FILE}")

    # 寫入 GitHub Step Summary
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(md_content)

if __name__ == "__main__":
    check_and_sort()

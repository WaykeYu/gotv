import os
import json
import requests
from datetime import datetime

# 目標檔案路徑
BOX_FILE = "box1.json"
NG_DIR = "collect/NG"

TIMEOUT = 5  # 逾時秒數 (可依需求調整)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def is_valid_url(url: str) -> bool:
    """檢測 URL 是否有效 (支援 http/https)"""
    if not url or not url.startswith(("http://", "https://")):
        return False
    try:
        # 先用 HEAD 請求快速檢查，若不支援則退回 GET (只讀開頭)
        resp = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code < 400:
            return True
        if resp.status_code in [403, 405]:
            resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=True)
            return resp.status_code < 400
    except Exception:
        return False
    return False

def check_channels():
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

    # 針對 TVBox 常見的 channels / urls 結構進行過濾
    # 若 JSON 結構不同，可調整此處 key (例如 data.get("lives", []))
    items = data.get("channels") or data.get("urls") or []
    
    valid_items = []
    invalid_items = []

    print(f"[{datetime.now()}] 開始檢測...")

    for item in items:
        # 相容字典形式 ({"name": "...", "url": "..."}) 或純字串形式
        url = item.get("url") if isinstance(item, dict) else item
        name = item.get("name", "未知") if isinstance(item, dict) else url

        if is_valid_url(url):
            valid_items.append(item)
            print(f"[OK] {name}")
        else:
            invalid_items.append({
                "item": item,
                "checked_at": datetime.now().isoformat()
            })
            print(f"[NG] {name} -> {url}")

    # 更新過濾後的資料
    if "channels" in data:
        data["channels"] = valid_items
    elif "urls" in data:
        data["urls"] = valid_items

    with open(BOX_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 儲存失效網址到 collect/NG/
    ng_filename = f"{NG_DIR}/ng_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    if invalid_items:
        with open(ng_filename, "w", encoding="utf-8") as f:
            json.dump(invalid_items, f, ensure_ascii=False, indent=2)

    # 輸出統計報告 (供 GitHub Actions Job Summary 呈現)
    total = len(items)
    ok_count = len(valid_items)
    ng_count = len(invalid_items)
    survival_rate = (ok_count / total * 100) if total > 0 else 0

    summary = f"""
### 📊 影音網址定時檢測報告
- **檢測時間**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **總檢查數**：{total}
- **有效數 (存活)**：{ok_count}
- **失效數 (移入 NG)**：{ng_count}
- **存活率**：{survival_rate:.2f}%
- **失效記錄檔**：`{ng_filename if invalid_items else '無新增失效網址'}`
"""
    print(summary)

    # 寫入 GitHub Step Summary
    summary_file = os.getenv("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(summary)

if __name__ == "__main__":
    check_channels()

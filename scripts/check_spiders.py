import os
import shutil
import json
import time
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime, date

# ================= 專案路徑設定 =================
BASE_DIR = Path(__file__).resolve().parent.parent
PY_DIR = BASE_DIR / "py"
JS_DIR = BASE_DIR / "js"
COLLECT_DIR = BASE_DIR / "collect"
REPORT_FILE = BASE_DIR / "SPIDER_STATUS.md"

BOX_PY_FILE = BASE_DIR / "box_py.json"
FUN_PY_FILE = BASE_DIR / "fun_py.json"
BOX_JS_FILE = BASE_DIR / "box_js.json"
FUN_JS_FILE = BASE_DIR / "fun_js.json"
BOX_CT_FILE = BASE_DIR / "box_ct.json"
FUN_CT_FILE = BASE_DIR / "fun_ct.json"

# 成人類特徵關鍵字
ADULT_KEYWORDS = [
    "成人", "福利", "18+", "18禁", "伦理", "倫理", 
    "情色", "av", "sex", "adult", "色情", "午夜", "限制"
]

TIMEOUT_SECONDS = 6
MAX_CONCURRENT_TASKS = 25


def load_fail_history(history_file: Path) -> dict:
    """讀取指定目錄的歷史失效日期紀錄"""
    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_fail_history(history_file: Path, history: dict):
    """儲存更新後的歷史失效紀錄"""
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def is_adult_content(data: dict, file_name: str) -> bool:
    """判斷配置內容、站點名稱或檔名是否屬於成人類別"""
    text_to_check = file_name.lower()
    
    sites = data.get("sites", [])
    for site in sites:
        name = str(site.get("name", "")).lower()
        site_type = str(site.get("type", "")).lower()
        api = str(site.get("api", "")).lower()
        text_to_check += f" {name} {site_type} {api}"

    return any(keyword in text_to_check for keyword in ADULT_KEYWORDS)


def extract_primary_url(content: dict) -> str:
    """提取配置中的主要連線 URL（spider/jar/api/wallpaper）"""
    spider = content.get("spider", "") or content.get("jar", "")
    if isinstance(spider, str) and spider.startswith(("http://", "https://")):
        return spider.strip()

    sites = content.get("sites", [])
    for site in sites:
        api = site.get("api", "")
        if isinstance(api, str) and api.startswith(("http://", "https://")):
            return api.strip()

    wallpaper = content.get("wallpaper", "")
    if isinstance(wallpaper, str) and wallpaper.startswith(("http://", "https://")):
        return wallpaper.strip()

    return ""


async def test_spider_speed(session: aiohttp.ClientSession, url: str) -> float | None:
    """測試 URL 響應速度，回傳毫秒；連線失敗或超時回傳 None"""
    if not url.startswith(("http://", "https://")):
        return None
    try:
        start_time = time.time()
        async with session.get(url, timeout=TIMEOUT_SECONDS, ssl=False) as response:
            if response.status in [200, 206, 301, 302]:
                elapsed_ms = (time.time() - start_time) * 1000
                return round(elapsed_ms, 2)
    except Exception:
        pass
    return None


def handle_failure(
    file_path: Path, 
    ng_dir: Path, 
    fail_history: dict, 
    today_str: str, 
    immediate: bool = False
) -> str:
    """
    處理檔案失效：
    - immediate=True（重覆或 JSON 格式毀損）：立即移入對應的 NG/
    - immediate=False（連線超時/失效）：檢查是否已跨日連續兩天失效，達標才移入對應的 NG/
    回傳狀態標記：'moved_ng' 或 'pending_day1'
    """
    ng_dir.mkdir(parents=True, exist_ok=True)
    target_ng_path = ng_dir / file_path.name
    file_key = file_path.name

    if immediate:
        fail_history.pop(file_key, None)
        if file_path.resolve() != target_ng_path.resolve():
            shutil.move(str(file_path), str(target_ng_path))
        return "moved_ng"

    first_fail_str = fail_history.get(file_key)
    if not first_fail_str:
        # 第一次失效，登記今天日期並留待觀察
        fail_history[file_key] = today_str
        return "pending_day1"

    # 計算首次失效至今的日曆天數差
    first_fail_date = date.fromisoformat(first_fail_str)
    today_date = date.fromisoformat(today_str)
    days_elapsed = (today_date - first_fail_date).days

    if days_elapsed >= 1:
        # 已跨越至第二天（或以上）仍檢測失效 -> 正式移入 NG
        fail_history.pop(file_key, None)
        if file_path.resolve() != target_ng_path.resolve():
            shutil.move(str(file_path), str(target_ng_path))
        return "moved_ng"
    else:
        # 同一天內重複執行腳本，維持觀察狀態
        return "pending_day1"


async def process_file(
    file_path: Path,
    ng_dir: Path,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    seen_urls: set,
    fail_history: dict,
    today_str: str
):
    """檢驗單一設定檔並執行去重、測速與跨日失效處置"""
    async with semaphore:
        # 1. 讀取並驗證 JSON 格式（毀損視為立即無效）
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = json.load(f)
        except Exception:
            status = handle_failure(file_path, ng_dir, fail_history, today_str, immediate=True)
            return {"_status": status, "file_name": file_path.name}

        # 2. 提取 URL 並判定重覆（重覆 URL 視為立即淘汰）
        primary_url = extract_primary_url(content)
        if not primary_url or primary_url in seen_urls:
            status = handle_failure(file_path, ng_dir, fail_history, today_str, immediate=True)
            return {"_status": status, "file_name": file_path.name}

        seen_urls.add(primary_url)

        # 3. 測試響應速度（連線失敗需連續兩天確認才移入 NG）
        speed = await test_spider_speed(session, primary_url)
        if speed is None:
            status = handle_failure(file_path, ng_dir, fail_history, today_str, immediate=False)
            return {"_status": status, "file_name": file_path.name}

        # 4. 連線成功：若先前有失效紀錄，立即清除觀察狀態
        fail_history.pop(file_path.name, None)

        is_adult = is_adult_content(content, file_path.name)
        return {
            "_status": "valid",
            "file_name": file_path.name,
            "origin_path": str(file_path),
            "response_time_ms": speed,
            "is_adult": is_adult,
            "url": primary_url,
            "data": content
        }


def save_and_split(entries: list, box_path: Path, fun_path: Path):
    """依一般類與成人類拆分，並按延遲由低到高排序寫入"""
    box_list = [e for e in entries if not e["is_adult"]]
    fun_list = [e for e in entries if e["is_adult"]]

    box_list.sort(key=lambda x: x["response_time_ms"])
    fun_list.sort(key=lambda x: x["response_time_ms"])

    with open(box_path, "w", encoding="utf-8") as f:
        json.dump([e["data"] for e in box_list], f, ensure_ascii=False, indent=2)

    with open(fun_path, "w", encoding="utf-8") as f:
        json.dump([e["data"] for e in fun_list], f, ensure_ascii=False, indent=2)

    return box_list, fun_list


async def process_directory(
    target_dir: Path,
    box_out: Path,
    fun_out: Path,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    seen_urls: set,
    today_str: str
) -> dict:
    """統一處理單一來源資料夾（PY / JS / COLLECT）的過濾、觀察與匯出"""
    ng_dir = target_dir / "NG"
    history_file = target_dir / ".fail_history.json"
    ng_dir.mkdir(parents=True, exist_ok=True)

    fail_history = load_fail_history(history_file)

    files = []
    if target_dir.exists():
        for f in target_dir.glob("*.json"):
            if f.parent != ng_dir and not f.name.startswith("."):
                files.append(f)

    tasks = [
        process_file(f, ng_dir, session, semaphore, seen_urls, fail_history, today_str)
        for f in files
    ]
    raw_results = await asyncio.gather(*tasks)

    valid_list = [r for r in raw_results if r and r.get("_status") == "valid"]
    pending_list = [r for r in raw_results if r and r.get("_status") == "pending_day1"]
    moved_list = [r for r in raw_results if r and r.get("_status") == "moved_ng"]

    box_list, fun_list = save_and_split(valid_list, box_out, fun_out)

    # 清理已不存在於該目錄的過期紀錄並存檔
    existing_names = {f.name for f in files}
    fail_history = {k: v for k, v in fail_history.items() if k in existing_names}
    save_fail_history(history_file, fail_history)

    return {
        "box": box_list,
        "fun": fun_list,
        "valid": valid_list,
        "pending_count": len(pending_list),
        "moved_count": len(moved_list),
        "ng_dir": ng_dir
    }


async def main():
    today_str = date.today().isoformat()
    seen_urls = set()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    conn = aiohttp.TCPConnector(ssl=False, limit=MAX_CONCURRENT_TASKS)

    async with aiohttp.ClientSession(connector=conn, headers=headers) as session:
        py_stat = await process_directory(PY_DIR, BOX_PY_FILE, FUN_PY_FILE, session, semaphore, seen_urls, today_str)
        js_stat = await process_directory(JS_DIR, BOX_JS_FILE, FUN_JS_FILE, session, semaphore, seen_urls, today_str)
        ct_stat = await process_directory(COLLECT_DIR, BOX_CT_FILE, FUN_CT_FILE, session, semaphore, seen_urls, today_str)

    # 產生 SPIDER_STATUS.md 狀態報告
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_lines = [
        "# Spider Status Report",
        f"> 更新時間：{now_str}\n",
        "### 統計摘要",
        f"- **PY 目錄**：一般類 `{len(py_stat['box'])}` 筆 / 成人類 `{len(py_stat['fun'])}` 筆（觀察中 `{py_stat['pending_count']}` 筆 / 移入 NG `{py_stat['moved_count']}` 筆）",
        f"- **JS 目錄**：一般類 `{len(js_stat['box'])}` 筆 / 成人類 `{len(js_stat['fun'])}` 筆（觀察中 `{js_stat['pending_count']}` 筆 / 移入 NG `{js_stat['moved_count']}` 筆）",
        f"- **COLLECT 目錄**：一般類 `{len(ct_stat['box'])}` 筆 / 成人類 `{len(ct_stat['fun'])}` 筆（觀察中 `{ct_stat['pending_count']}` 筆 / 移入 NG `{ct_stat['moved_count']}` 筆）\n",
        "### 響應速度前 5 名 (COLLECT)",
        "| 檔案名稱 | 響應時間 (ms) | 類別 |",
        "| :--- | :--- | :--- |"
    ]

    all_ct = sorted(ct_stat["valid"], key=lambda x: x["response_time_ms"])
    for item in all_ct[:5]:
        cat_name = "成人類" if item["is_adult"] else "一般類"
        report_lines.append(f"| {item['file_name']} | {item['response_time_ms']} ms | {cat_name} |")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")

    print("\n所有目錄檢測與分類完成：")
    print(f"- [PY] -> {BOX_PY_FILE.name} ({len(py_stat['box'])}), {FUN_PY_FILE.name} ({len(py_stat['fun'])}) | 觀察中: {py_stat['pending_count']} | 移入 NG: {py_stat['moved_count']}")
    print(f"- [JS] -> {BOX_JS_FILE.name} ({len(js_stat['box'])}), {FUN_JS_FILE.name} ({len(js_stat['fun'])}) | 觀察中: {js_stat['pending_count']} | 移入 NG: {js_stat['moved_count']}")
    print(f"- [CT] -> {BOX_CT_FILE.name} ({len(ct_stat['box'])}), {FUN_CT_FILE.name} ({len(ct_stat['fun'])}) | 觀察中: {ct_stat['pending_count']} | 移入 NG: {ct_stat['moved_count']}")


if __name__ == "__main__":
    asyncio.run(main())

import os
import re
import ssl
import shutil
import json
import time
import asyncio
import urllib.request
import urllib.error
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
    "情色", "av", "sex", "adult", "色情", "午夜", "限制", "私密"
]

TIMEOUT_SECONDS = 8
MAX_CONCURRENT_TASKS = 20

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def load_fail_history(history_file: Path) -> dict:
    if history_file.exists():
        try:
            with open(history_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_fail_history(history_file: Path, history: dict):
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def parse_flexible_content(file_path: Path):
    """
    彈性解析檔案：
    支援標準 JSON、含 // 註解的 JSONC，以及純文字網址清單
    """
    raw_text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw_text:
        return None

    # 1. 嘗試直接解析 JSON
    try:
        return json.loads(raw_text)
    except Exception:
        pass

    # 2. 移除 // 單行註解後再嘗試解析 JSONC
    cleaned_lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        # 移除行尾註解（避開 http:// 與 https://）
        line_no_comment = re.sub(r'(?<!:)\/\/.*$', '', line)
        cleaned_lines.append(line_no_comment)
    cleaned_text = "\n".join(cleaned_lines)

    try:
        return json.loads(cleaned_text)
    except Exception:
        pass

    # 3. 若為純文字清單（每行一個網址），轉換為標準格式字典
    urls = re.findall(r'https?://[^\s"\'<>]+', raw_text)
    if urls:
        return {"url": urls[0], "name": file_path.stem, "_raw_urls": urls}

    return None


def extract_primary_url(content) -> str:
    """從各種可能的欄位結構中提取主要檢測 URL"""
    if isinstance(content, list) and len(content) > 0:
        first = content[0]
        if isinstance(first, dict):
            return extract_primary_url(first)
        elif isinstance(first, str) and first.startswith(("http://", "https://")):
            return first.strip()

    if not isinstance(content, dict):
        return ""

    # 依序檢查常見的頂層鍵值
    for key in ["url", "spider", "jar", "api", "wallpaper", "live"]:
        val = content.get(key, "")
        if isinstance(val, str) and val.startswith(("http://", "https://")):
            # 處理 spider 常見的 "http://xxx.jar;md5;xxxx" 格式，僅取網址本體測速
            return val.split(";")[0].strip()

    # 檢查多倉 urls 陣列
    urls_list = content.get("urls", [])
    if isinstance(urls_list, list):
        for item in urls_list:
            if isinstance(item, dict) and str(item.get("url", "")).startswith(("http://", "https://")):
                return item["url"].split(";")[0].strip()
            elif isinstance(item, str) and item.startswith(("http://", "https://")):
                return item.split(";")[0].strip()

    # 檢查 sites 站點陣列
    sites = content.get("sites", [])
    if isinstance(sites, list):
        for site in sites:
            if isinstance(site, dict):
                api = str(site.get("api", ""))
                if api.startswith(("http://", "https://")):
                    return api.split(";")[0].strip()

    return ""


def is_adult_content(content, file_name: str) -> bool:
    """判斷是否屬於成人類別"""
    text_to_check = f"{file_name} {json.dumps(content, ensure_ascii=False)}".lower()
    return any(keyword in text_to_check for keyword in ADULT_KEYWORDS)


def _sync_check_url(url: str) -> tuple[float | None, str]:
    """測試 URL 連線速度，回傳 (毫秒延遲, 狀態說明)"""
    if not url.startswith(("http://", "https://")):
        return None, "無效網址格式"

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "okhttp/4.12.0",  # TVBox 常用 UA，避免被專擋瀏覽器的來源封鎖
            "Accept": "*/*",
            "Connection": "keep-alive"
        }
    )
    try:
        start_time = time.time()
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=SSL_CONTEXT) as response:
            elapsed_ms = (time.time() - start_time) * 1000
            if response.status < 400:
                return round(elapsed_ms, 2), f"HTTP {response.status}"
            return None, f"HTTP {response.status}"
    except urllib.error.HTTPError as e:
        # 部分伺服器不支援直接 GET 根目錄但回傳 403/405，代表主機仍在線
        if e.code in [403, 405]:
            return 999.0, f"HTTP {e.code} (主機在線)"
        return None, f"HTTP Error {e.code}"
    except Exception as e:
        return None, f"連線異常: {type(e).__name__}"


async def test_spider_speed(url: str) -> tuple[float | None, str]:
    return await asyncio.to_thread(_sync_check_url, url)


def record_or_move_failure(
    file_path: Path,
    ng_dir: Path,
    fail_history: dict,
    today_str: str,
    reason: str,
    immediate: bool = False,
    dry_run_move: bool = False
) -> str:
    """記錄首次失效日期；僅在跨日連續兩天失效（或明確重覆）時移入 NG"""
    file_key = file_path.name
    target_ng_path = ng_dir / file_key

    if immediate:
        fail_history.pop(file_key, None)
        if not dry_run_move and file_path.resolve() != target_ng_path.resolve():
            shutil.move(str(file_path), str(target_ng_path))
        print(f"  [立即移入NG] {file_key} -> 原因: {reason}")
        return "moved_ng"

    first_fail_str = fail_history.get(file_key)
    if not first_fail_str:
        fail_history[file_key] = today_str
        print(f"  [第1天失效觀察] {file_key} -> 原因: {reason}")
        return "pending_day1"

    days_elapsed = (date.fromisoformat(today_str) - date.fromisoformat(first_fail_str)).days
    if days_elapsed >= 1:
        fail_history.pop(file_key, None)
        if not dry_run_move and file_path.resolve() != target_ng_path.resolve():
            shutil.move(str(file_path), str(target_ng_path))
        print(f"  [連續{days_elapsed + 1}天失效移入NG] {file_key} -> 原因: {reason}")
        return "moved_ng"
    else:
        print(f"  [當日複檢仍失效] {file_key} -> 原因: {reason}")
        return "pending_day1"


async def process_file(
    file_path: Path,
    ng_dir: Path,
    semaphore: asyncio.Semaphore,
    seen_urls: set,
    fail_history: dict,
    today_str: str
):
    async with semaphore:
        content = parse_flexible_content(file_path)
        if content is None:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, "無法解析內容或空檔", immediate=True)
            return {"_status": status, "file_name": file_path.name}

        primary_url = extract_primary_url(content)
        if not primary_url:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, "檔案內找不到有效網址", immediate=True)
            return {"_status": status, "file_name": file_path.name}

        if primary_url in seen_urls:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, f"網址重覆 ({primary_url})", immediate=True)
            return {"_status": status, "file_name": file_path.name}

        seen_urls.add(primary_url)

        speed, msg = await test_spider_speed(primary_url)
        if speed is None:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, f"{msg} ({primary_url})", immediate=False)
            return {"_status": status, "file_name": file_path.name}

        # 連線成功，清除歷史失效紀錄
        fail_history.pop(file_path.name, None)

        return {
            "_status": "valid",
            "file_name": file_path.name,
            "response_time_ms": speed,
            "is_adult": is_adult_content(content, file_path.name),
            "url": primary_url,
            "data": content
        }


def save_and_split(entries: list, box_path: Path, fun_path: Path):
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
    semaphore: asyncio.Semaphore,
    seen_urls: set,
    today_str: str
) -> dict:
    print(f"\n>>> 開始掃描目錄：{target_dir.name}/")
    ng_dir = target_dir / "NG"
    history_file = target_dir / ".fail_history.json"
    ng_dir.mkdir(parents=True, exist_ok=True)

    fail_history = load_fail_history(history_file)

    files = []
    if target_dir.exists():
        # 同時支援 .json 與 .txt
        for ext in ("*.json", "*.txt"):
            for f in target_dir.glob(ext):
                if f.parent != ng_dir and not f.name.startswith("."):
                    files.append(f)

    tasks = [
        process_file(f, ng_dir, semaphore, seen_urls, fail_history, today_str)
        for f in files
    ]
    raw_results = await asyncio.gather(*tasks)

    valid_list = [r for r in raw_results if r and r.get("_status") == "valid"]
    pending_list = [r for r in raw_results if r and r.get("_status") == "pending_day1"]
    moved_list = [r for r in raw_results if r and r.get("_status") == "moved_ng"]

    box_list, fun_list = save_and_split(valid_list, box_out, fun_out)

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

    py_stat = await process_directory(PY_DIR, BOX_PY_FILE, FUN_PY_FILE, semaphore, seen_urls, today_str)
    js_stat = await process_directory(JS_DIR, BOX_JS_FILE, FUN_JS_FILE, semaphore, seen_urls, today_str)
    ct_stat = await process_directory(COLLECT_DIR, BOX_CT_FILE, FUN_CT_FILE, semaphore, seen_urls, today_str)

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

    print("\n==========================================")
    print("所有目錄檢測與分類完成！")


if __name__ == "__main__":
    asyncio.run(main())

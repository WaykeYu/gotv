import os
import re
import ast
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

# 六大分類輸出檔
BOX_PY_FILE = BASE_DIR / "box_py.json"
FUN_PY_FILE = BASE_DIR / "fun_py.json"
BOX_JS_FILE = BASE_DIR / "box_js.json"
FUN_JS_FILE = BASE_DIR / "fun_js.json"
BOX_CT_FILE = BASE_DIR / "box_ct.json"
FUN_CT_FILE = BASE_DIR / "fun_ct.json"

# 成人類特徵關鍵字
ADULT_KEYWORDS = [
    "成人", "福利", "18+", "18禁", "伦理", "倫理", "情色", "色情",
    "av", "sex", "adult", "porn", "xxx", "午夜", "限制", "私密",
    "里番", "無碼", "无码", "有碼", "有码", "女優", "女优", "蜜桃", "麻豆"
]

# ================= 廣告攔截規則庫 =================
ADS_DOMAINS = [
    "mimg.0c1q0l.cn", "www.googletagmanager.com", "www.google-analytics.com",
    "mc.usihnbcq.cn", "mg.g1mm3d.cn", "mscs.svaeuzh.cn", "cnzz.hhttm.top",
    "tp.vinuxhome.com", "cnzz.mmstat.com", "www.baihuillq.com", "s23.cnzz.com",
    "z3.cnzz.com", "c.cnzz.com", "stj.v1vo.top", "z12.cnzz.com", "img.mosflower.cn",
    "tips.gamevvip.com", "ehwe.yhdtns.com", "xdn.cqqc3.com", "www.jixunkyy.cn",
    "sp.chemacid.cn", "hm.baidu.com", "s9.cnzz.com", "z6.cnzz.com", "um.cavuc.com",
    "mav.mavuz.com", "wofwk.aoidf3.com", "z5.cnzz.com", "xc.hubeijieshikj.cn",
    "tj.tianwenhu.com", "xg.gars57.cn", "k.jinxiuzhilv.com", "cdn.bootcss.com",
    "ppl.xunzhuo123.com", "xomk.jiangjunmh.top", "img.xunzhuo123.com", "z1.cnzz.com",
    "s13.cnzz.com", "xg.huataisangao.cn", "z7.cnzz.com", "z2.cnzz.com",
    "s96.cnzz.com", "q11.cnzz.com", "thy.dacedsfa.cn", "xg.whsbpw.cn",
    "s19.cnzz.com", "z8.cnzz.com", "s4.cnzz.com", "f5w.as12df.top", "ae01.alicdn.com",
    "www.92424.cn", "k.wudejia.com", "vivovip.mmszxc.top", "qiu.xixiqiu.com",
    "cdnjs.hnfenxun.com", "cms.qdwght.com", "api.htpan.net",
    "googlesyndication.com", "doubleclick.net", "adservice.google.com",
    "pagead2.googlesyndication.com", "umeng.com", "log.aliyuncs.com"
]

AD_RULES = [
    {
        "name": "量子廣告攔截",
        "hosts": ["vip.lz", "hd.lz", "v.cdnlz", "cdnlz"],
        "regex": ["18.5333", "#EXT-X-DISCONTINUITY\\r*\\n*#EXTINF:6.433333,[\\s\\S]*?#EXT-X-DISCONTINUITY"]
    },
    {
        "name": "非凡廣告攔截",
        "hosts": ["vip.ffzy", "hd.ffzy", "ffzy"],
        "regex": ["25.0666", "25.08", "#EXT-X-DISCONTINUITY\\r*\\n*#EXTINF:25.066667,[\\s\\S]*?#EXT-X-DISCONTINUITY"]
    },
    {
        "name": "暴風廣告攔截",
        "hosts": ["bfzy", "s5.bfzycdn"],
        "regex": ["#EXT-X-DISCONTINUITY\\r*\\n*#EXTINF:3,[\\s\\S]*?#EXT-X-DISCONTINUITY"]
    },
    {
        "name": "索尼廣告攔截",
        "hosts": ["suonizy", "snzy"],
        "regex": ["15.1666", "15.2666", "#EXT-X-DISCONTINUITY\\r*\\n*#EXTINF:15.266667,[\\s\\S]*?#EXT-X-DISCONTINUITY"]
    },
    {
        "name": "通用切片廣告過濾",
        "hosts": ["m3u8"],
        "regex": ["#EXT-X-DISCONTINUITY\\r*\\n*#EXTINF:5.000000,[\\s\\S]*?#EXT-X-DISCONTINUITY"]
    }
]

TIMEOUT_SECONDS = 8
MAX_CONCURRENT_TASKS = 20

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def attach_adblock(payload: dict) -> dict:
    """為匯出的 JSON 結構加上廣告攔截規則 (ads 與 rules)"""
    payload["ads"] = list(ADS_DOMAINS)
    payload["rules"] = [dict(r) for r in AD_RULES]
    return payload


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


def check_is_adult(text_content: str, file_name: str) -> bool:
    combined = f"{file_name} {text_content}".lower()
    return any(keyword in combined for keyword in ADULT_KEYWORDS)


def _sync_check_url(url: str) -> tuple[float | None, str, str]:
    """測試 URL 連線速度並抓取部分回應內容供分類判定"""
    if not url.startswith(("http://", "https://")):
        return None, "無效網址格式", ""

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "okhttp/4.12.0",
            "Accept": "*/*",
            "Connection": "keep-alive"
        }
    )
    try:
        start_time = time.time()
        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS, context=SSL_CONTEXT) as response:
            elapsed_ms = (time.time() - start_time) * 1000
            if response.status < 400:
                raw_bytes = response.read(16384)
                snippet = raw_bytes.decode("utf-8", errors="ignore")
                return round(elapsed_ms, 2), f"HTTP {response.status}", snippet
            return None, f"HTTP {response.status}", ""
    except urllib.error.HTTPError as e:
        if e.code in [403, 405]:
            return 999.0, f"HTTP {e.code} (主機在線)", ""
        return None, f"HTTP Error {e.code}", ""
    except Exception as e:
        return None, f"連線異常: {type(e).__name__}", ""


async def test_spider_speed(url: str) -> tuple[float | None, str, str]:
    return await asyncio.to_thread(_sync_check_url, url)


def record_or_move_failure(
    file_path: Path,
    ng_dir: Path,
    fail_history: dict,
    today_str: str,
    reason: str,
    immediate: bool = False
) -> str:
    """記錄首次失效日期；僅在跨日連續兩天失效（或明確損毀/重覆）時移入 NG"""
    file_key = file_path.name
    target_ng_path = ng_dir / file_key

    if immediate:
        fail_history.pop(file_key, None)
        if file_path.resolve() != target_ng_path.resolve():
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
        if file_path.resolve() != target_ng_path.resolve():
            shutil.move(str(file_path), str(target_ng_path))
        print(f"  [連續{days_elapsed + 1}天失效移入NG] {file_key} -> 原因: {reason}")
        return "moved_ng"
    else:
        print(f"  [當日複檢仍失效] {file_key} -> 原因: {reason}")
        return "pending_day1"


def extract_url_from_script(code_text: str) -> str:
    """從 .py 或 .js 腳本中提取目標站點 URL 進行存活性測試"""
    patterns = [
        r'(?:host|url|baseUrl|base_url|siteUrl|api)\s*[:=]\s*["\'](https?://[^"\'\s]+)["\']',
        r'["\'](https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}[^"\'\s]*)["\']'
    ]
    ignore_domains = ("w3.org", "github.com", "githubusercontent.com", "mozilla.org", "google.com", "example.com")
    
    for pat in patterns:
        matches = re.findall(pat, code_text, re.IGNORECASE)
        for m in matches:
            if not any(ig in m.lower() for ig in ignore_domains):
                return m.strip()
    return ""


async def process_script_file(
    file_path: Path,
    script_type: str,
    ng_dir: Path,
    semaphore: asyncio.Semaphore,
    fail_history: dict,
    today_str: str
):
    """處理 PY 或 JS 爬蟲腳本：檢查語法、提取目標站點測速、並封裝為 TVBox site 條目"""
    async with semaphore:
        raw_code = file_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not raw_code:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, "空白腳本檔案", immediate=True)
            return {"_status": status, "file_name": file_path.name}

        if script_type == "py":
            try:
                ast.parse(raw_code)
            except SyntaxError as e:
                status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, f"Python 語法錯誤: {e.msg}", immediate=True)
                return {"_status": status, "file_name": file_path.name}

        target_url = extract_url_from_script(raw_code)
        snippet = ""
        if target_url:
            speed, msg, snippet = await test_spider_speed(target_url)
            if speed is None:
                status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, f"目標站點失效 {msg} ({target_url})", immediate=False)
                return {"_status": status, "file_name": file_path.name}
        else:
            speed = 500.0

        fail_history.pop(file_path.name, None)

        title_match = re.search(r'(?:title|name)\s*[:=]\s*["\']([^"\']+)["\']', raw_code)
        site_name = title_match.group(1).strip() if title_match else file_path.stem

        is_adult = check_is_adult(f"{raw_code} {snippet}", file_path.name)

        raw_github_url = f"https://raw.githubusercontent.com/WaykeYu/gotv/main/{script_type}/{file_path.name}"
        site_entry = {
            "key": f"{script_type}_{file_path.stem}",
            "name": f"{site_name}({script_type.upper()})",
            "type": 3,
            "api": raw_github_url,
            "searchable": 1,
            "quickSearch": 1,
            "filterable": 1
        }

        return {
            "_status": "valid",
            "file_name": file_path.name,
            "response_time_ms": speed,
            "is_adult": is_adult,
            "site_entry": site_entry
        }


def parse_flexible_content(file_path: Path):
    """彈性解析 COLLECT 設定檔：支援 JSON、JSONC 及純文字網址"""
    raw_text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw_text:
        return None
    try:
        return json.loads(raw_text)
    except Exception:
        pass

    cleaned_lines = [
        re.sub(r'(?<!:)\/\/.*$', '', line)
        for line in raw_text.splitlines()
        if not line.strip().startswith(("//", "#"))
    ]
    try:
        return json.loads("\n".join(cleaned_lines))
    except Exception:
        pass

    urls = re.findall(r'https?://[^\s"\'<>]+', raw_text)
    if urls:
        return {"url": urls[0], "name": file_path.stem}
    return None


def extract_primary_url_and_name(content, fallback_name: str) -> tuple[str, str]:
    """提取網址與顯示名稱，供組裝標準多倉格式使用"""
    if isinstance(content, list) and content:
        return extract_primary_url_and_name(content[0], fallback_name)
    if not isinstance(content, dict):
        return "", fallback_name

    name = str(content.get("name") or fallback_name).strip()

    for key in ["url", "spider", "jar", "api", "wallpaper", "live"]:
        val = content.get(key, "")
        if isinstance(val, str) and val.startswith(("http://", "https://")):
            return val.split(";")[0].strip(), name

    for list_key in ["urls", "sites"]:
        items = content.get(list_key, [])
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    u = str(item.get("url") or item.get("api") or "")
                    item_name = str(item.get("name") or name).strip()
                    if u.startswith(("http://", "https://")):
                        return u.split(";")[0].strip(), item_name
    return "", name


async def process_collect_file(
    file_path: Path,
    ng_dir: Path,
    semaphore: asyncio.Semaphore,
    seen_urls: set,
    fail_history: dict,
    today_str: str
):
    """處理 COLLECT 目錄下的訂閱/配置檔"""
    async with semaphore:
        content = parse_flexible_content(file_path)
        if content is None:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, "無法解析內容或空檔", immediate=True)
            return {"_status": status, "file_name": file_path.name}

        primary_url, display_name = extract_primary_url_and_name(content, file_path.stem)
        if not primary_url:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, "找不到有效網址", immediate=True)
            return {"_status": status, "file_name": file_path.name}

        if primary_url in seen_urls:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, f"網址重覆 ({primary_url})", immediate=True)
            return {"_status": status, "file_name": file_path.name}

        seen_urls.add(primary_url)

        speed, msg, remote_snippet = await test_spider_speed(primary_url)
        if speed is None:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, f"{msg} ({primary_url})", immediate=False)
            return {"_status": status, "file_name": file_path.name}

        fail_history.pop(file_path.name, None)

        local_str = json.dumps(content, ensure_ascii=False)
        is_adult = check_is_adult(f"{local_str} {remote_snippet}", file_path.name)

        return {
            "_status": "valid",
            "file_name": file_path.name,
            "name": display_name,
            "url": primary_url,
            "response_time_ms": speed,
            "is_adult": is_adult
        }


def save_script_output(entries: list, box_path: Path, fun_path: Path):
    """匯出 box_py.json / fun_py.json 與 box_js.json / fun_js.json，並各自加上廣告攔截"""
    box_entries = sorted([e for e in entries if not e["is_adult"]], key=lambda x: x["response_time_ms"])
    fun_entries = sorted([e for e in entries if e["is_adult"]], key=lambda x: x["response_time_ms"])

    for target_list, out_file in [(box_entries, box_path), (fun_entries, fun_path)]:
        output_obj = attach_adblock({
            "spider": "",
            "sites": [e["site_entry"] for e in target_list]
        })
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output_obj, f, ensure_ascii=False, indent=2)

    return box_entries, fun_entries


def save_collect_output(entries: list, box_path: Path, fun_path: Path):
    """匯出 box_ct.json 與 fun_ct.json（標準多倉格式），並各自加上廣告攔截"""
    box_entries = sorted([e for e in entries if not e["is_adult"]], key=lambda x: x["response_time_ms"])
    fun_entries = sorted([e for e in entries if e["is_adult"]], key=lambda x: x["response_time_ms"])

    for target_list, out_file in [(box_entries, box_path), (fun_entries, fun_path)]:
        multi_repo_obj = attach_adblock({
            "urls": [
                {
                    "url": e["url"],
                    "name": f"{e['name']} [{int(e['response_time_ms'])}ms]"
                }
                for e in target_list
            ]
        })
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(multi_repo_obj, f, ensure_ascii=False, indent=2)

    return box_entries, fun_entries


async def run_script_dir(target_dir: Path, script_type: str, box_out: Path, fun_out: Path, semaphore: asyncio.Semaphore, today_str: str) -> dict:
    print(f"\n>>> 開始掃描腳本目錄：{target_dir.name}/ (*.{script_type})")
    ng_dir = target_dir / "NG"
    history_file = target_dir / ".fail_history.json"
    ng_dir.mkdir(parents=True, exist_ok=True)

    fail_history = load_fail_history(history_file)
    files = []
    if target_dir.exists():
        for f in target_dir.glob(f"*.{script_type}"):
            if f.parent != ng_dir and not f.name.startswith((".", "__")):
                files.append(f)

    tasks = [process_script_file(f, script_type, ng_dir, semaphore, fail_history, today_str) for f in files]
    raw_results = await asyncio.gather(*tasks)

    valid_list = [r for r in raw_results if r and r.get("_status") == "valid"]
    pending_list = [r for r in raw_results if r and r.get("_status") == "pending_day1"]
    moved_list = [r for r in raw_results if r and r.get("_status") == "moved_ng"]

    box_list, fun_list = save_script_output(valid_list, box_out, fun_out)

    existing_names = {f.name for f in files}
    fail_history = {k: v for k, v in fail_history.items() if k in existing_names}
    save_fail_history(history_file, fail_history)

    return {
        "box": box_list,
        "fun": fun_list,
        "pending_count": len(pending_list),
        "moved_count": len(moved_list)
    }


async def run_collect_dir(target_dir: Path, box_out: Path, fun_out: Path, semaphore: asyncio.Semaphore, seen_urls: set, today_str: str) -> dict:
    print(f"\n>>> 開始掃描訂閱目錄：{target_dir.name}/")
    ng_dir = target_dir / "NG"
    history_file = target_dir / ".fail_history.json"
    ng_dir.mkdir(parents=True, exist_ok=True)

    fail_history = load_fail_history(history_file)
    files = []
    if target_dir.exists():
        for ext in ("*.json", "*.txt"):
            for f in target_dir.glob(ext):
                if f.parent != ng_dir and not f.name.startswith("."):
                    files.append(f)

    tasks = [process_collect_file(f, ng_dir, semaphore, seen_urls, fail_history, today_str) for f in files]
    raw_results = await asyncio.gather(*tasks)

    valid_list = [r for r in raw_results if r and r.get("_status") == "valid"]
    pending_list = [r for r in raw_results if r and r.get("_status") == "pending_day1"]
    moved_list = [r for r in raw_results if r and r.get("_status") == "moved_ng"]

    box_list, fun_list = save_collect_output(valid_list, box_out, fun_out)

    existing_names = {f.name for f in files}
    fail_history = {k: v for k, v in fail_history.items() if k in existing_names}
    save_fail_history(history_file, fail_history)

    return {
        "box": box_list,
        "fun": fun_list,
        "pending_count": len(pending_list),
        "moved_count": len(moved_list)
    }


async def main():
    today_str = date.today().isoformat()
    seen_urls = set()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

    # 分別處理 PY (*.py)、JS (*.js)、COLLECT (*.json / *.txt)，各自寫入廣告攔截規則
    py_stat = await run_script_dir(PY_DIR, "py", BOX_PY_FILE, FUN_PY_FILE, semaphore, today_str)
    js_stat = await run_script_dir(JS_DIR, "js", BOX_JS_FILE, FUN_JS_FILE, semaphore, today_str)
    ct_stat = await run_collect_dir(COLLECT_DIR, BOX_CT_FILE, FUN_CT_FILE, semaphore, seen_urls, today_str)

    # 產生報告
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_lines = [
        "# Spider Status Report",
        f"> 更新時間：{now_str}（六支匯出檔案皆已內建廣告攔截 `ads` 與 `rules`）\n",
        "### 統計摘要",
        f"- **PY 目錄**：一般類 `{len(py_stat['box'])}` 筆 / 成人類 `{len(py_stat['fun'])}` 筆（觀察中 `{py_stat['pending_count']}` 筆 / 移入 NG `{py_stat['moved_count']}` 筆）",
        f"- **JS 目錄**：一般類 `{len(js_stat['box'])}` 筆 / 成人類 `{len(js_stat['fun'])}` 筆（觀察中 `{js_stat['pending_count']}` 筆 / 移入 NG `{js_stat['moved_count']}` 筆）",
        f"- **COLLECT 目錄**：一般類 `{len(ct_stat['box'])}` 筆 / 成人類 `{len(ct_stat['fun'])}` 筆（觀察中 `{ct_stat['pending_count']}` 筆 / 移入 NG `{ct_stat['moved_count']}` 筆）\n",
        "### 響應速度前 5 名 (COLLECT - 一般類)",
        "| 檔案名稱 | 響應時間 (ms) |",
        "| :--- | :--- |"
    ]

    for item in ct_stat["box"][:5]:
        report_lines.append(f"| {item['file_name']} | {item['response_time_ms']} ms |")

    report_lines.extend([
        "\n### 響應速度前 5 名 (COLLECT - 成人類)",
        "| 檔案名稱 | 響應時間 (ms) |",
        "| :--- | :--- |"
    ])

    for item in ct_stat["fun"][:5]:
        report_lines.append(f"| {item['file_name']} | {item['response_time_ms']} ms |")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines) + "\n")

    print("\n==========================================")
    print("六支配置檔（box/fun_py, box/fun_js, box/fun_ct）皆已加上廣告攔截並匯出完成！")


if __name__ == "__main__":
    asyncio.run(main())

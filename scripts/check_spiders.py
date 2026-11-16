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

# 六大分類輸出檔
BOX_PY_FILE = BASE_DIR / "box_py.json"
FUN_PY_FILE = BASE_DIR / "fun_py.json"
BOX_JS_FILE = BASE_DIR / "box_js.json"
FUN_JS_FILE = BASE_DIR / "fun_js.json"
BOX_CT_FILE = BASE_DIR / "box_ct.json"
FUN_CT_FILE = BASE_DIR / "fun_ct.json"

# 統合廣告攔截共用檔
ADBLOCK_FILE = BASE_DIR / "adblock.json"

# 成人類特徵關鍵字（涵蓋繁簡中文、英文與常見影視源暗語）
ADULT_KEYWORDS = [
    "成人", "福利", "18+", "18禁", "伦理", "倫理", "情色", "色情",
    "av", "sex", "adult", "porn", "xxx", "午夜", "限制", "私密",
    "里番", "無碼", "无码", "有碼", "有码", "女優", "女优", "蜜桃", "麻豆"
]

# ================= 統合廣告攔截設定中心 =================
UNIFIED_ADBLOCK = {
    "ads": [
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
    ],
    "rules": [
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
}

TIMEOUT_SECONDS = 8
MAX_CONCURRENT_TASKS = 20

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def apply_unified_adblock(config_data):
    """統合廣告攔截：將 UNIFIED_ADBLOCK 合併進設定檔，避免重複與遺漏"""
    if not isinstance(config_data, dict):
        return config_data

    # 合併 ads 網域黑名單
    old_ads = config_data.get("ads") if isinstance(config_data.get("ads"), list) else []
    config_data["ads"] = list(dict.fromkeys(old_ads + UNIFIED_ADBLOCK["ads"]))

    # 合併 rules 切片過濾規則
    old_rules = config_data.get("rules") if isinstance(config_data.get("rules"), list) else []
    existing_names = {r.get("name") for r in old_rules if isinstance(r, dict)}
    for rule in UNIFIED_ADBLOCK["rules"]:
        if rule["name"] not in existing_names:
            old_rules.append(rule)
    config_data["rules"] = old_rules

    return config_data


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
    """彈性解析檔案：支援標準 JSON、含 // 註解的 JSONC，以及純文字網址清單"""
    raw_text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not raw_text:
        return None

    try:
        return json.loads(raw_text)
    except Exception:
        pass

    cleaned_lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("#"):
            continue
        line_no_comment = re.sub(r'(?<!:)\/\/.*$', '', line)
        cleaned_lines.append(line_no_comment)
    cleaned_text = "\n".join(cleaned_lines)

    try:
        return json.loads(cleaned_text)
    except Exception:
        pass

    urls = re.findall(r'https?://[^\s"\'<>]+', raw_text)
    if urls:
        return {"url": urls[0], "name": file_path.stem}

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

    for key in ["url", "spider", "jar", "api", "wallpaper", "live"]:
        val = content.get(key, "")
        if isinstance(val, str) and val.startswith(("http://", "https://")):
            return val.split(";")[0].strip()

    urls_list = content.get("urls", [])
    if isinstance(urls_list, list):
        for item in urls_list:
            if isinstance(item, dict) and str(item.get("url", "")).startswith(("http://", "https://")):
                return item["url"].split(";")[0].strip()
            elif isinstance(item, str) and item.startswith(("http://", "https://")):
                return item.split(";")[0].strip()

    sites = content.get("sites", [])
    if isinstance(sites, list):
        for site in sites:
            if isinstance(site, dict):
                api = str(site.get("api", ""))
                if api.startswith(("http://", "https://")):
                    return api.split(";")[0].strip()

    return ""


def check_is_adult(content, file_name: str, remote_snippet: str = "") -> bool:
    """綜合比對：檔名 + 本地內容 + 遠端抓取內容，精準區分成人類與一般類"""
    local_str = json.dumps(content, ensure_ascii=False) if not isinstance(content, str) else content
    combined_text = f"{file_name} {local_str} {remote_snippet}".lower()
    return any(keyword in combined_text for keyword in ADULT_KEYWORDS)


def _sync_check_url(url: str) -> tuple[float | None, str, str]:
    """
    測試 URL 連線速度並抓取部分回應內容供分類判定
    回傳：(毫秒延遲, 狀態說明, 遠端內容片段)
    """
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
                # 讀取前 16KB 文本內容供成人/一般分類辨識
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
    """記錄首次失效日期；僅在跨日連續兩天失效（或明確重覆）時移入 NG"""
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

        speed, msg, remote_snippet = await test_spider_speed(primary_url)
        if speed is None:
            status = record_or_move_failure(file_path, ng_dir, fail_history, today_str, f"{msg} ({primary_url})", immediate=False)
            return {"_status": status, "file_name": file_path.name}

        fail_history.pop(file_path.name, None)

        # 結合遠端回傳內容進行成人/一般分類判定
        is_adult = check_is_adult(content, file_path.name, remote_snippet)

        # 統合注入廣告攔截規則
        enriched_content = apply_unified_adblock(content)

        return {
            "_status": "valid",
            "file_name": file_path.name,
            "response_time_ms": speed,
            "is_adult": is_adult,
            "url": primary_url,
            "data": enriched_content
        }


def save_and_split(entries: list, box_path: Path, fun_path: Path):
    """分拆一般類 (box) 與成人類 (fun)，各自按響應速度由快到慢排序匯出"""
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

    # 1. 獨立匯出一份全專案統合廣告攔截檔 adblock.json
    with open(ADBLOCK_FILE, "w", encoding="utf-8") as f:
        json.dump(UNIFIED_ADBLOCK, f, ensure_ascii=False, indent=2)

    # 2. 分別檢測並產出 PY / JS / COLLECT 的一般類與成人類配置
    py_stat = await process_directory(PY_DIR, BOX_PY_FILE, FUN_PY_FILE, semaphore, seen_urls, today_str)
    js_stat = await process_directory(JS_DIR, BOX_JS_FILE, FUN_JS_FILE, semaphore, seen_urls, today_str)
    ct_stat = await process_directory(COLLECT_DIR, BOX_CT_FILE, FUN_CT_FILE, semaphore, seen_urls, today_str)

    # 3. 更新狀態報告
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_lines = [
        "# Spider Status Report",
        f"> 更新時間：{now_str}（已統合廣告攔截規則至 `adblock.json` 及各配置檔）\n",
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
    print(f"一般類 box_ct.json：{len(ct_stat['box'])} 筆 | 成人類 fun_ct.json：{len(ct_stat['fun'])} 筆")
    print(f"統合廣告攔截規則已匯出至：{ADBLOCK_FILE.name}")


if __name__ == "__main__":
    asyncio.run(main())

# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`2026-11-08 03:45:51`  
> 🛠️ **檢測核心**：`curl_cffi (JA3偽裝)` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **31** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **35** | **32** | **3** | **31** | **0** | `91.4%` | **636.5 ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**9** 站 (28.1%)
- 🟡 **良好** (`300 ~ 600ms`)：**11** 站 (34.4%)
- 🟠 **普通** (`600 ~ 1000ms`)：**6** 站 (18.8%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**6** 站 (18.8%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | `飄零 | 采集` | **83.4** | 🟢 極速 | `403 (CF在線放行)` | `https://p2100.net/api.php/provide/vod/` |
| 2 | `芒果 | 采集` | **190.5** | 🟢 極速 | `code:1 (成功)` | `https://caiji.mgzyapi.com/api.php/provide/vod/` |
| 3 | `天涯 | 采集` | **222.5** | 🟢 極速 | `code:1 (成功)` | `https://tyyszyapi.com/api.php/provide/vod/` |
| 4 | `牛牛 | 采集` | **227.5** | 🟢 極速 | `code:1 (成功)` | `https://api.niuniuzy.me/api.php/provide/vod/` |
| 5 | `快车 | 采集` | **247.3** | 🟢 極速 | `code:1 (成功)` | `https://caiji.kuaichezy.org/api.php/provide/vod/` |
| 6 | `ok | 采集` | **280.1** | 🟢 極速 | `code:1 (成功)` | `https://api.okzyw.net/api.php/provide/vod/` |
| 7 | `索尼 | 采集` | **280.2** | 🟢 極速 | `code:1 (成功)` | `https://suoniapi.com/api.php/provide/vod/` |
| 8 | `鸭鸭 | 采集` | **286.0** | 🟢 極速 | `code:1 (成功)` | `https://cj.yayazy.net/api.php/provide/vod/` |
| 9 | `百度云 | 采集` | **291.5** | 🟢 極速 | `code:1 (成功)` | `https://api.apibdzy.com/api.php/provide/vod` |
| 10 | `红牛 | 采集` | **309.7** | 🟡 良好 | `code:1 (成功)` | `http://hongniuzy2.com/api.php/provide/vod/` |
| 11 | `极速 | 采集` | **313.1** | 🟡 良好 | `code:1 (成功)` | `https://jszyapi.com/api.php/provide/vod/` |
| 12 | `豪华 | 采集` | **343.8** | 🟡 良好 | `code:1 (成功)` | `https://hhzyapi.com/api.php/provide/vod/` |
| 13 | `魔都 | 采集` | **375.5** | 🟡 良好 | `code:1 (成功)` | `https://www.mdzyapi.com/api.php/provide/vod/` |
| 14 | `樱花 | 采集` | **387.6** | 🟡 良好 | `code:1 (成功)` | `https://m3u8.apiyhzy.com/api.php/provide/vod/` |
| 15 | `新浪 | 采集` | **467.8** | 🟡 良好 | `code:1 (成功)` | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/` |
| 16 | `虎牙 | 采集` | **476.5** | 🟡 良好 | `code:1 (成功)` | `https://www.huyaapi.com/api.php/provide/vod/` |
| 17 | `无尽 | 采集` | **481.3** | 🟡 良好 | `code:1 (成功)` | `https://api.wujinapi.net/api.php/provide/vod/` |
| 18 | `速播 | 采集` | **482.8** | 🟡 良好 | `code:1 (成功)` | `https://subocaiji.com/api.php/provide/vod/` |
| 19 | `金鹰 | 采集` | **493.7** | 🟡 良好 | `code:1 (成功)` | `https://jyzyapi.com/api.php/provide/vod/` |
| 20 | `光速 | 采集` | **544.3** | 🟡 良好 | `code:1 (成功)` | `https://api.guangsuapi.com/api.php/provide/vod/` |
| 21 | `优质 | 采集` | **602.6** | 🟠 普通 | `code:1 (成功)` | `https://api.yyzy-tv.vip/inc/apijson.php` |
| 22 | `最大 | 采集` | **686.6** | 🟠 普通 | `code:1 (成功)` | `https://api.zuidapi.com/api.php/provide/vod/from/zuidam...` |
| 23 | `猫眼 | 采集` | **722.3** | 🟠 普通 | `code:1 (成功)` | `https://api.maoyanapi.top/api.php/provide/vod/` |
| 24 | `暴風 | 采集` | **726.6** | 🟠 普通 | `code:1 (成功)` | `https://bfzyapi.com/api.php/provide/vod/` |
| 25 | `ikun | 采集` | **800.4** | 🟠 普通 | `code:1 (成功)` | `https://ikunzyapi.com/api.php/provide/vod/` |
| 26 | `量子 | 采集` | **933.7** | 🟠 普通 | `code:1 (成功)` | `https://cj.lziapi.com/api.php/provide/vod/` |
| 27 | `艾旦 | 采集` | **1088.6** | 🔴 遲鈍 | `code:1 (成功)` | `https://www.lovedan.net/api.php/provide/vod/` |
| 28 | `厂长 | 采集` | **1225.9** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.changzhang.tv/api.php/provide/vod/` |
| 29 | `母鸡 | 采集` | **1294.8** | 🔴 遲鈍 | `code:1 (成功)` | `https://mujiziyuan00.com/api.php/provide/vod/` |
| 30 | `巨量 | 采集` | **1566.6** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.juliang.live/api/provide/vod/` |
| 31 | `非凡 | 采集` | **1818.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://liuyan.ffzy3.tv/api.php/provide/vod/` |
| 32 | `创享 | 采集` | **2115.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://ys.cxkjg.cn/api/provide/vod/` |

---

### ⚠️ 本次移入 NG 項目 (共 3 筆)
> 📦 **封存檔案**：`collect/NG/box1_ng_20261108_034617.json`

| 站點名稱 | 移入原因 | 網址預覽 |
| :--- | :--- | :--- |
| `茅台 | 采集` | `例外: DNSError` | `https://mtzy.me/api.php/provide/vod/` |
| `360 | 采集` | `連線逾時 (Timeout)` | `https://360zy.com/api.php/provide/vod/` |
| `爱奇艺 | 采集` | `連線逾時 (Timeout)` | `https://www.iqiyizyapi.com/api.php/provide/vod/` |

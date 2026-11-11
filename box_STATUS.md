# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`2026-11-12 06:24:02`  
> 🛠️ **檢測核心**：`curl_cffi (JA3偽裝)` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **31** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **34** | **32** | **2** | **31** | **0** | `94.1%` | **510.4 ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**13** 站 (40.6%)
- 🟡 **良好** (`300 ~ 600ms`)：**10** 站 (31.2%)
- 🟠 **普通** (`600 ~ 1000ms`)：**4** 站 (12.5%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**5** 站 (15.6%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | `飄零 | 采集` | **67.4** | 🟢 極速 | `403 (CF在線放行)` | `https://p2100.net/api.php/provide/vod/` |
| 2 | `快车 | 采集` | **120.3** | 🟢 極速 | `code:1 (成功)` | `https://caiji.kuaichezy.org/api.php/provide/vod/` |
| 3 | `ikun | 采集` | **141.8** | 🟢 極速 | `code:1 (成功)` | `https://ikunzyapi.com/api.php/provide/vod/` |
| 4 | `红牛 | 采集` | **156.8** | 🟢 極速 | `code:1 (成功)` | `http://hongniuzy2.com/api.php/provide/vod/` |
| 5 | `牛牛 | 采集` | **161.8** | 🟢 極速 | `code:1 (成功)` | `https://api.niuniuzy.me/api.php/provide/vod/` |
| 6 | `百度云 | 采集` | **165.8** | 🟢 極速 | `code:1 (成功)` | `https://api.apibdzy.com/api.php/provide/vod` |
| 7 | `无尽 | 采集` | **176.0** | 🟢 極速 | `code:1 (成功)` | `https://api.wujinapi.net/api.php/provide/vod/` |
| 8 | `天涯 | 采集` | **192.4** | 🟢 極速 | `code:1 (成功)` | `https://tyyszyapi.com/api.php/provide/vod/` |
| 9 | `鸭鸭 | 采集` | **195.4** | 🟢 極速 | `code:1 (成功)` | `https://cj.yayazy.net/api.php/provide/vod/` |
| 10 | `索尼 | 采集` | **214.0** | 🟢 極速 | `code:1 (成功)` | `https://suoniapi.com/api.php/provide/vod/` |
| 11 | `芒果 | 采集` | **245.8** | 🟢 極速 | `code:1 (成功)` | `https://caiji.mgzyapi.com/api.php/provide/vod/` |
| 12 | `ok | 采集` | **262.4** | 🟢 極速 | `code:1 (成功)` | `https://api.okzyw.net/api.php/provide/vod/` |
| 13 | `豪华 | 采集` | **282.9** | 🟢 極速 | `code:1 (成功)` | `https://hhzyapi.com/api.php/provide/vod/` |
| 14 | `樱花 | 采集` | **305.4** | 🟡 良好 | `code:1 (成功)` | `https://m3u8.apiyhzy.com/api.php/provide/vod/` |
| 15 | `极速 | 采集` | **331.7** | 🟡 良好 | `code:1 (成功)` | `https://jszyapi.com/api.php/provide/vod/` |
| 16 | `暴風 | 采集` | **343.0** | 🟡 良好 | `code:1 (成功)` | `https://bfzyapi.com/api.php/provide/vod/` |
| 17 | `新浪 | 采集` | **399.8** | 🟡 良好 | `code:1 (成功)` | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/` |
| 18 | `速播 | 采集` | **436.5** | 🟡 良好 | `code:1 (成功)` | `https://subocaiji.com/api.php/provide/vod/` |
| 19 | `金鹰 | 采集` | **479.9** | 🟡 良好 | `code:1 (成功)` | `https://jyzyapi.com/api.php/provide/vod/` |
| 20 | `虎牙 | 采集` | **483.1** | 🟡 良好 | `code:1 (成功)` | `https://www.huyaapi.com/api.php/provide/vod/` |
| 21 | `光速 | 采集` | **513.2** | 🟡 良好 | `code:1 (成功)` | `https://api.guangsuapi.com/api.php/provide/vod/` |
| 22 | `优质 | 采集` | **561.8** | 🟡 良好 | `code:1 (成功)` | `https://api.yyzy-tv.vip/inc/apijson.php` |
| 23 | `厂长 | 采集` | **567.0** | 🟡 良好 | `code:1 (成功)` | `https://api.changzhang.tv/api.php/provide/vod/` |
| 24 | `猫眼 | 采集` | **618.3** | 🟠 普通 | `code:1 (成功)` | `https://api.maoyanapi.top/api.php/provide/vod/` |
| 25 | `艾旦 | 采集` | **696.9** | 🟠 普通 | `code:1 (成功)` | `https://www.lovedan.net/api.php/provide/vod/` |
| 26 | `最大 | 采集` | **716.1** | 🟠 普通 | `code:1 (成功)` | `https://api.zuidapi.com/api.php/provide/vod/from/zuidam...` |
| 27 | `量子 | 采集` | **745.9** | 🟠 普通 | `code:1 (成功)` | `https://cj.lziapi.com/api.php/provide/vod/` |
| 28 | `母鸡 | 采集` | **1065.6** | 🔴 遲鈍 | `code:1 (成功)` | `https://mujiziyuan00.com/api.php/provide/vod/` |
| 29 | `360 | 采集` | **1217.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://360zy.com/api.php/provide/vod/` |
| 30 | `巨量 | 采集` | **1273.0** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.juliang.live/api/provide/vod/` |
| 31 | `非凡 | 采集` | **1573.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://liuyan.ffzy3.tv/api.php/provide/vod/` |
| 32 | `创享 | 采集` | **1623.7** | 🔴 遲鈍 | `code:1 (成功)` | `https://ys.cxkjg.cn/api/provide/vod/` |

---

### ⚠️ 本次移入 NG 項目 (共 2 筆)
> 📦 **封存檔案**：`collect/NG/box1_ng_20261112_062428.json`

| 站點名稱 | 移入原因 | 網址預覽 |
| :--- | :--- | :--- |
| `爱奇艺 | 采集` | `HTTP 504` | `https://www.iqiyizyapi.com/api.php/provide/vod/` |
| `魔都 | 采集` | `連線逾時 (Timeout)` | `https://www.mdzyapi.com/api.php/provide/vod/` |

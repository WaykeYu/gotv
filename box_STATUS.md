# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`2026-11-07 05:11:55`  
> 🛠️ **檢測核心**：`curl_cffi (JA3偽裝)` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **34** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **35** | **35** | **0** | **34** | **0** | `100.0%` | **801.6 ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**6** 站 (17.1%)
- 🟡 **良好** (`300 ~ 600ms`)：**12** 站 (34.3%)
- 🟠 **普通** (`600 ~ 1000ms`)：**8** 站 (22.9%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**9** 站 (25.7%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | `飄零 | 采集` | **148.3** | 🟢 極速 | `403 (CF在線放行)` | `https://p2100.net/api.php/provide/vod/` |
| 2 | `ok | 采集` | **214.8** | 🟢 極速 | `code:1 (成功)` | `https://api.okzyw.net/api.php/provide/vod/` |
| 3 | `ikun | 采集` | **240.8** | 🟢 極速 | `code:1 (成功)` | `https://ikunzyapi.com/api.php/provide/vod/` |
| 4 | `魔都 | 采集` | **254.9** | 🟢 極速 | `code:1 (成功)` | `https://www.mdzyapi.com/api.php/provide/vod/` |
| 5 | `百度云 | 采集` | **260.5** | 🟢 極速 | `code:1 (成功)` | `https://api.apibdzy.com/api.php/provide/vod` |
| 6 | `天涯 | 采集` | **290.7** | 🟢 極速 | `code:1 (成功)` | `https://tyyszyapi.com/api.php/provide/vod/` |
| 7 | `无尽 | 采集` | **319.1** | 🟡 良好 | `code:1 (成功)` | `https://api.wujinapi.net/api.php/provide/vod/` |
| 8 | `快车 | 采集` | **324.3** | 🟡 良好 | `code:1 (成功)` | `https://caiji.kuaichezy.org/api.php/provide/vod/` |
| 9 | `索尼 | 采集` | **347.0** | 🟡 良好 | `code:1 (成功)` | `https://suoniapi.com/api.php/provide/vod/` |
| 10 | `红牛 | 采集` | **358.4** | 🟡 良好 | `code:1 (成功)` | `http://hongniuzy2.com/api.php/provide/vod/` |
| 11 | `牛牛 | 采集` | **360.4** | 🟡 良好 | `code:1 (成功)` | `https://api.niuniuzy.me/api.php/provide/vod/` |
| 12 | `芒果 | 采集` | **365.3** | 🟡 良好 | `code:1 (成功)` | `https://caiji.mgzyapi.com/api.php/provide/vod/` |
| 13 | `豪华 | 采集` | **373.3** | 🟡 良好 | `code:1 (成功)` | `https://hhzyapi.com/api.php/provide/vod/` |
| 14 | `樱花 | 采集` | **382.7** | 🟡 良好 | `code:1 (成功)` | `https://m3u8.apiyhzy.com/api.php/provide/vod/` |
| 15 | `鸭鸭 | 采集` | **384.3** | 🟡 良好 | `code:1 (成功)` | `https://cj.yayazy.net/api.php/provide/vod/` |
| 16 | `极速 | 采集` | **426.5** | 🟡 良好 | `code:1 (成功)` | `https://jszyapi.com/api.php/provide/vod/` |
| 17 | `新浪 | 采集` | **528.1** | 🟡 良好 | `code:1 (成功)` | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/` |
| 18 | `虎牙 | 采集` | **571.4** | 🟡 良好 | `code:1 (成功)` | `https://www.huyaapi.com/api.php/provide/vod/` |
| 19 | `金鹰 | 采集` | **615.9** | 🟠 普通 | `code:1 (成功)` | `https://jyzyapi.com/api.php/provide/vod/` |
| 20 | `光速 | 采集` | **631.2** | 🟠 普通 | `code:1 (成功)` | `https://api.guangsuapi.com/api.php/provide/vod/` |
| 21 | `暴風 | 采集` | **672.8** | 🟠 普通 | `code:1 (成功)` | `https://bfzyapi.com/api.php/provide/vod/` |
| 22 | `速播 | 采集` | **734.3** | 🟠 普通 | `code:1 (成功)` | `https://subocaiji.com/api.php/provide/vod/` |
| 23 | `最大 | 采集` | **741.4** | 🟠 普通 | `code:1 (成功)` | `https://api.zuidapi.com/api.php/provide/vod/from/zuidam...` |
| 24 | `猫眼 | 采集` | **753.1** | 🟠 普通 | `code:1 (成功)` | `https://api.maoyanapi.top/api.php/provide/vod/` |
| 25 | `优质 | 采集` | **792.1** | 🟠 普通 | `code:1 (成功)` | `https://api.yyzy-tv.vip/inc/apijson.php` |
| 26 | `艾旦 | 采集` | **972.2** | 🟠 普通 | `code:1 (成功)` | `https://www.lovedan.net/api.php/provide/vod/` |
| 27 | `360 | 采集` | **1141.8** | 🔴 遲鈍 | `code:1 (成功)` | `https://360zy.com/api.php/provide/vod/` |
| 28 | `厂长 | 采集` | **1228.9** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.changzhang.tv/api.php/provide/vod/` |
| 29 | `量子 | 采集` | **1314.1** | 🔴 遲鈍 | `code:1 (成功)` | `https://cj.lziapi.com/api.php/provide/vod/` |
| 30 | `母鸡 | 采集` | **1455.7** | 🔴 遲鈍 | `code:1 (成功)` | `https://mujiziyuan00.com/api.php/provide/vod/` |
| 31 | `茅台 | 采集` | **1900.1** | 🔴 遲鈍 | `code:1 (成功)` | `https://mtzy.me/api.php/provide/vod/` |
| 32 | `爱奇艺 | 采集` | **1952.5** | 🔴 遲鈍 | `code:1 (成功)` | `https://www.iqiyizyapi.com/api.php/provide/vod/` |
| 33 | `非凡 | 采集` | **2030.5** | 🔴 遲鈍 | `code:1 (成功)` | `https://liuyan.ffzy3.tv/api.php/provide/vod/` |
| 34 | `巨量 | 采集` | **2298.3** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.juliang.live/api/provide/vod/` |
| 35 | `创享 | 采集` | **2671.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://ys.cxkjg.cn/api/provide/vod/` |

# 📊 box1.json 影音來源檢測與響應統計表

> 🕒 **檢測時間 (UTC+8)**：`2026-11-13 05:59:01`  
> 🛠️ **檢測核心**：`curl_cffi (JA3偽裝)` (含 code:1 優先判定與 WAF 403 存活放行)  
> ⚡ **排序規則**：已依連線響應延遲時間（由快到慢）完成重新排序回存。  
> 🎯 **成功特徵命中**：檢測內文包含 `"code":1` 的採集源共有 **31** 個。

---

### 📈 綜合健康指標看板

| 總檢測數 | 🟢 存活站點 | 🔴 移入 NG | 🎯 命中 code:1 | 🔁 重複過濾 | 📊 存活率 | ⚡ 平均延遲 |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **32** | **32** | **0** | **31** | **0** | `100.0%` | **603.7 ms** |

#### ⏱️ 響應延遲區間分佈
- 🟢 **極速** (`< 300ms`)：**12** 站 (37.5%)
- 🟡 **良好** (`300 ~ 600ms`)：**11** 站 (34.4%)
- 🟠 **普通** (`600 ~ 1000ms`)：**4** 站 (12.5%)
- 🔴 **遲鈍** (`≥ 1000ms`)：**5** 站 (15.6%)

---

### 🚀 有效來源排行榜（已按響應速度排序回存）

| # | 站點名稱 | 延遲 (ms) | 評級 | 狀態碼 / 特徵 | 網址預覽 |
| :-: | :--- | :-: | :-: | :--- | :--- |
| 1 | `飄零 | 采集` | **93.2** | 🟢 極速 | `403 (CF在線放行)` | `https://p2100.net/api.php/provide/vod/` |
| 2 | `芒果 | 采集` | **205.0** | 🟢 極速 | `code:1 (成功)` | `https://caiji.mgzyapi.com/api.php/provide/vod/` |
| 3 | `百度云 | 采集` | **226.7** | 🟢 極速 | `code:1 (成功)` | `https://api.apibdzy.com/api.php/provide/vod` |
| 4 | `红牛 | 采集` | **228.7** | 🟢 極速 | `code:1 (成功)` | `http://hongniuzy2.com/api.php/provide/vod/` |
| 5 | `快车 | 采集` | **230.8** | 🟢 極速 | `code:1 (成功)` | `https://caiji.kuaichezy.org/api.php/provide/vod/` |
| 6 | `ok | 采集` | **241.4** | 🟢 極速 | `code:1 (成功)` | `https://api.okzyw.net/api.php/provide/vod/` |
| 7 | `ikun | 采集` | **244.1** | 🟢 極速 | `code:1 (成功)` | `https://ikunzyapi.com/api.php/provide/vod/` |
| 8 | `天涯 | 采集` | **255.9** | 🟢 極速 | `code:1 (成功)` | `https://tyyszyapi.com/api.php/provide/vod/` |
| 9 | `牛牛 | 采集` | **257.6** | 🟢 極速 | `code:1 (成功)` | `https://api.niuniuzy.me/api.php/provide/vod/` |
| 10 | `索尼 | 采集` | **270.0** | 🟢 極速 | `code:1 (成功)` | `https://suoniapi.com/api.php/provide/vod/` |
| 11 | `鸭鸭 | 采集` | **297.8** | 🟢 極速 | `code:1 (成功)` | `https://cj.yayazy.net/api.php/provide/vod/` |
| 12 | `无尽 | 采集` | **299.0** | 🟢 極速 | `code:1 (成功)` | `https://api.wujinapi.net/api.php/provide/vod/` |
| 13 | `豪华 | 采集` | **375.4** | 🟡 良好 | `code:1 (成功)` | `https://hhzyapi.com/api.php/provide/vod/` |
| 14 | `极速 | 采集` | **380.7** | 🟡 良好 | `code:1 (成功)` | `https://jszyapi.com/api.php/provide/vod/` |
| 15 | `优质 | 采集` | **449.3** | 🟡 良好 | `code:1 (成功)` | `https://api.yyzy-tv.vip/inc/apijson.php` |
| 16 | `樱花 | 采集` | **482.8** | 🟡 良好 | `code:1 (成功)` | `https://m3u8.apiyhzy.com/api.php/provide/vod/` |
| 17 | `速播 | 采集` | **506.3** | 🟡 良好 | `code:1 (成功)` | `https://subocaiji.com/api.php/provide/vod/` |
| 18 | `艾旦 | 采集` | **513.7** | 🟡 良好 | `code:1 (成功)` | `https://www.lovedan.net/api.php/provide/vod/` |
| 19 | `新浪 | 采集` | **544.2** | 🟡 良好 | `code:1 (成功)` | `https://api.xinlangapi.com/xinlangapi.php/provide/vod/` |
| 20 | `光速 | 采集` | **564.3** | 🟡 良好 | `code:1 (成功)` | `https://api.guangsuapi.com/api.php/provide/vod/` |
| 21 | `虎牙 | 采集` | **569.3** | 🟡 良好 | `code:1 (成功)` | `https://www.huyaapi.com/api.php/provide/vod/` |
| 22 | `厂长 | 采集` | **591.2** | 🟡 良好 | `code:1 (成功)` | `https://api.changzhang.tv/api.php/provide/vod/` |
| 23 | `金鹰 | 采集` | **596.4** | 🟡 良好 | `code:1 (成功)` | `https://jyzyapi.com/api.php/provide/vod/` |
| 24 | `最大 | 采集` | **667.2** | 🟠 普通 | `code:1 (成功)` | `https://api.zuidapi.com/api.php/provide/vod/from/zuidam...` |
| 25 | `暴風 | 采集` | **675.9** | 🟠 普通 | `code:1 (成功)` | `https://bfzyapi.com/api.php/provide/vod/` |
| 26 | `猫眼 | 采集` | **693.9** | 🟠 普通 | `code:1 (成功)` | `https://api.maoyanapi.top/api.php/provide/vod/` |
| 27 | `360 | 采集` | **907.6** | 🟠 普通 | `code:1 (成功)` | `https://360zy.com/api.php/provide/vod/` |
| 28 | `量子 | 采集` | **1089.2** | 🔴 遲鈍 | `code:1 (成功)` | `https://cj.lziapi.com/api.php/provide/vod/` |
| 29 | `母鸡 | 采集` | **1366.7** | 🔴 遲鈍 | `code:1 (成功)` | `https://mujiziyuan00.com/api.php/provide/vod/` |
| 30 | `巨量 | 采集` | **1685.3** | 🔴 遲鈍 | `code:1 (成功)` | `https://api.juliang.live/api/provide/vod/` |
| 31 | `非凡 | 采集` | **1834.4** | 🔴 遲鈍 | `code:1 (成功)` | `https://liuyan.ffzy3.tv/api.php/provide/vod/` |
| 32 | `创享 | 采集` | **1974.0** | 🔴 遲鈍 | `code:1 (成功)` | `https://ys.cxkjg.cn/api/provide/vod/` |

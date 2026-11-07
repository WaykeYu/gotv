var rule = {
    title: '楓林網',
    host: 'https://imaple.tv',
    url: '/vodshow/fyfilter--------fypage---.html',
    // 備用無篩選路由
    // url: '/vodtype/fyclass-fypage.html',
    searchUrl: '/vodsearch/-------------.html?wd=**',
    searchable: 2,
    quickSearch: 0,
    filterable: 1,
    headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://imaple.tv/',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    },
    timeout: 10000,
    class_name: '電影&電視劇&綜藝&動漫',
    class_url: '1&2&3&4',
    // 篩選器字典定義
    filter: {
        "1": [
            {"key": "class", "name": "劇情", "value": [
                {"n": "全部", "v": ""}, {"n": "動作", "v": "動作"}, {"n": "喜劇", "v": "喜劇"},
                {"n": "愛情", "v": "愛情"}, {"n": "科幻", "v": "科幻"}, {"n": "恐怖", "v": "恐怖"},
                {"n": "劇情", "v": "劇情"}, {"n": "戰爭", "v": "戰爭"}, {"n": "動畫", "v": "動畫"}
            ]},
            {"key": "area", "name": "地區", "value": [
                {"n": "全部", "v": ""}, {"n": "台灣", "v": "台灣"}, {"n": "香港", "v": "香港"},
                {"n": "大陸", "v": "大陸"}, {"n": "韓國", "v": "韓國"}, {"n": "日本", "v": "日本"},
                {"n": "美國", "v": "美國"}
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "按時間", "v": "time"}, {"n": "按人氣", "v": "hits"}, {"n": "按評分", "v": "score"}
            ]}
        ],
        "2": [
            {"key": "class", "name": "劇情", "value": [
                {"n": "全部", "v": ""}, {"n": "台劇", "v": "台劇"}, {"n": "韓劇", "v": "韓劇"},
                {"n": "陸劇", "v": "陸劇"}, {"n": "日劇", "v": "日劇"}, {"n": "美劇", "v": "美劇"},
                {"n": "港劇", "v": "港劇"}
            ]},
            {"key": "area", "name": "地區", "value": [
                {"n": "全部", "v": ""}, {"n": "台灣", "v": "台灣"}, {"n": "香港", "v": "香港"},
                {"n": "大陸", "v": "大陸"}, {"n": "韓國", "v": "韓國"}, {"n": "日本", "v": "日本"},
                {"n": "美國", "v": "美國"}
            ]},
            {"key": "by", "name": "排序", "value": [
                {"n": "按時間", "v": "time"}, {"n": "按人氣", "v": "hits"}, {"n": "按評分", "v": "score"}
            ]}
        ]
    },
    filter_url: '{{fl.area}}-{{fl.by}}-{{fl.class}}-----fypage---{{fl.year}}',
    limit: 20,
    play_parse: true,
    // 嗅探規則 (支援直接放行 m3u8 / mp4)
    sniffer: 1,
    isVideo: 'http((?!http).){12,}?\\.(m3u8|mp4)\\?.*|http((?!http).){12,}?\\.(m3u8|mp4)',

    // 1. 分類與列表頁解析
    // 格式：卡片元素; 標題; 圖片; 副標題/狀態; 詳情頁連結
    一级: '.module-item, .public-list-box; a&&title; .module-item-pic img, .lazy&&data-src||src; .module-item-note, .ft2&&Text; a&&href',

    // 2. 詳情頁解析
    二级: {
        title: 'h1&&Text',
        img: '.module-item-pic img, .lazy&&data-src||src',
        desc: '.module-info-introduction-content, .desc&&Text',
        content: '.module-info-introduction-content, .desc&&Text',
        tabs: '.module-tab-item, .anthology-tab a',
        lists: '.module-list:eq(#id) a, .anthology-list-box:eq(#id) a'
    },

    // 3. 搜尋頁解析
    搜索: '.module-item, .public-list-box; a&&title; img&&data-src||src; .module-item-note&&Text; a&&href',

    // 4. 二次解析 / 免嗅探跳轉邏輯
    lazy: $js.toString(() => {
        let playUrl = input;
        // 如果傳入的已經是 m3u8/mp4 直連
        if (/\.(m3u8|mp4)/.test(playUrl)) {
            input = { parse: 0, url: playUrl, header: rule.headers };
        } else {
            // 抓取播放頁取得 player_aaaa 配置
            let html = request(playUrl);
            let m = html.match(/player_aaaa\s*=\s*({.*?})</) || html.match(/player_aaaa\s*=\s*({.*?});/);
            if (m) {
                try {
                    let cfg = JSON.parse(m[1]);
                    let vUrl = cfg.url || '';
                    if (cfg.encrypt === '1' || cfg.encrypt === 1) {
                        vUrl = unescape(vUrl);
                    } else if (cfg.encrypt === '2' || cfg.encrypt === 2) {
                        vUrl = unescape(base64Decode(vUrl));
                    }
                    if (/\.(m3u8|mp4)/.test(vUrl)) {
                        input = { parse: 0, url: vUrl, header: rule.headers };
                    } else {
                        // 交給 TVBox 內建 WebView 嗅探落地
                        input = { parse: 1, url: vUrl || playUrl, header: rule.headers };
                    }
                } catch (e) {
                    input = { parse: 1, url: playUrl, header: rule.headers };
                }
            } else {
                input = { parse: 1, url: playUrl, header: rule.headers };
            }
        }
    })
};

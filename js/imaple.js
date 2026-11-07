/**
 * imaple.tv 增強版爬蟲規則 (相容 TVBox / FongMi / CatVod T3)
 */
var rule = {
    title: '楓林網',
    host: 'https://imaple.tv',
    // 支援通用分類與直接載入分類首頁
    url: '/fyclass/page/fypage.html[/fyclass/index.html]',
    searchUrl: '/vodsearch/-------------.html?wd=**',
    searchable: 2,
    quickSearch: 0,
    filterable: 0,

    headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://imaple.tv/',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    },

    class_name: '電影&電視劇&動漫&綜藝',
    class_url: 'movie&drama&anime&show',

    // 容錯選擇器：依序嘗試 module-item、box-item、item 與一般卡片
    推薦: '.module-items .module-item, .box-item-list .box-item, .myui-vodlist__box;a&&title||a&&text;img&&data-original||img&&data-src||img&&src;.module-item-text&&Text||.pic-text&&Text;a&&href',

    一級: '.module-items .module-item, .box-item-list .box-item, .myui-vodlist__box;a&&title||a&&text;img&&data-original||img&&data-src||img&&src;.module-item-text&&Text||.pic-text&&Text;a&&href',

    二級: {
        title: 'h1&&Text||.page-title&&Text',
        img: '.module-item-pic img&&data-original||.module-item-pic img&&data-src||.picture img&&src||img.lazyload&&data-original',
        desc: '.video-info-items:contains(年代) div&&Text||.data:contains(年份)&&Text;;;.video-info-items:contains(導演) div&&Text||.data:contains(導演)&&Text;.video-info-items:contains(主演) div&&Text||.data:contains(主演)&&Text',
        content: '.module-info-introduction-content p&&Text||.desc-content p&&Text||#desc p&&Text||.sketch&&Text',
        // 多播放來源標籤相容
        tabs: '.module-tab-item, .nav-tabs li, .play-source-tab a',
        // 集數清單相容
        lists: '.module-player-list:eq(#id) a, .myui-content__list:eq(#id) a, .playlist:eq(#id) a'
    },

    // 播放解析：啟用 TVBox 內部 WebView 嗅探，並設定過濾關鍵字
    play_parse: true,
    lazy: `js:
        input = {
            parse: 1,
            url: input,
            header: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://imaple.tv/'
            }
        };
    `,

    搜尋: '.module-card-item, .module-item, .search-box-item;a&&title||a&&text;img&&data-original||img&&data-src||img&&src;.module-card-item-tag&&Text||.pic-text&&Text;a&&href'
};

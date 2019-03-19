var _userAgent = navigator.userAgent;
var platform = {
    isWeiXin: /MicroMessenger/i.test(_userAgent),
    isMobile: /iphone|ipod|ipad|ipad|Android|nokia|blackberry|webos|webos|webmate|bada|lg|ucweb/i.test(_userAgent),
    isIos: /iPhone|iPad|iPod|iOS/i.test(_userAgent),
    isIphone: /iPhone/i.test(_userAgent),
    isXX: /xxAssistant/i.test(_userAgent),
    isXXipa: /xxipa/ig.test(_userAgent) && /(iPhone|iPod|iPad|ios)/ig.test(_userAgent),
    isSafari: /safari/ig.test(_userAgent) && !/(crios|chrome|fxios|qqbrowser|sogou|baidu|ucbrowser|qhbrowser|opera|micromessenger|weibo)/ig
        .test(_userAgent),
};

function urlKey() {
    var search = {};
    location.search.replace(/([^=&?]*)=([^&]*)/g, function (str, key, value) {
        search[key] = decodeURIComponent(value).replace(/</g, "&lt;").replace(/>/g, "&gt;")
    });
    return search;
}

function setCookie(cname, cvalue, exdays) {
    var d = new Date();
    d.setTime(d.getTime() + (exdays * 24 * 60 * 60 * 1000));
    var expires = "expires=" + d.toUTCString();
    document.cookie = cname + "=" + cvalue + "; " + expires + "; path=/;domain=.xxkuwan.cn";
}

function getCookie(name) {
    var reg = new RegExp(name + '=([^;]*)'),
        arr = document.cookie.match(reg);
    return arr && arr[1];
}

function param(data) {
    // If this is not an object, defer to native stringification.
    if (Object.prototype.toString.call(data) !== "[object Object]") {
        return "error=error";
    }
    var buffer = [];
    for (var name in data) {
        if (!data.hasOwnProperty(name)) {
            continue;
        }
        var value = data[name];
        buffer.push(
            encodeURIComponent(name) + "=" + encodeURIComponent((value == null) ? "" : value));
    }
    var source = buffer.join("&").replace(/%20/g, "+");
    return (source);
}

function rewriteHref(arr) {
    var _k = urlKey().sid;
    setCookie("xxsessionid", _k, 60);
    Object.prototype.toString.call(arr) == "[object Array]" && JSON.stringify(G.urlKey) !== "{}" && arr.forEach(function (
        v, i) {
        G.urlKey.hasOwnProperty(v) && delete G.urlKey[v];
    })
    // 如果跳转ipa设置完sid  清除链接上的参数
    if (urlKey().from && urlKey().from == "setsid") {
        history.replaceState && history.replaceState(null, "", window.location.origin + (param(G.urlKey) == "" ? "" :
            "?" + param(G.urlKey)));
    } else {
        window.location.href = "//ipa.xxzhushou.cn/setsid.html?back=" + encodeURIComponent(window.location.href) +
            "&sid=" + _k;
    }
}
var channel = {
    '001': {
        'i': 'http://ipa.xxzhushou.cn/?channelid=62890',
        'a': 'http://downapk.mapping.xxzhushou.cn/com.min.sdk_61202.apk'
    },
    '002': {
        'i': 'http://ipa.xxzhushou.cn/?channelid=64890',
        'a': 'http://downapk.mapping.xxzhushou.cn/com.xxAssistant_64886.apk'
    },
    '003': {
        'i': 'http://ipa.xxzhushou.cn/?channelid=64892',
        'a': 'http://downapk.mapping.xxzhushou.cn/com.xxAssistant_64888.apk'
    },
    '004': {
        'i': 'http://ipa.xxzhushou.cn/?channelid=75216',
        'a': 'http://downapk.mapping.xxzhushou.cn/com.xxAssistant_75214.apk'
    },
    '005': {
        'i': 'http://ipa.xxzhushou.cn/?channelid=75218',
        'a': 'http://downapk.mapping.xxzhushou.cn/com.xxAssistant_75212.apk'
    }
}
window.G = {
    urlKey: urlKey(),
    platform: platform,
    channel: channel[urlKey().cid || '001'] || channel[001],
    setCookie: setCookie,
    getCookie: getCookie,
    rewriteHref: rewriteHref
};
define('page/m/m', function (require, exports, module) {

    'use strict';

    if (!G.platform.isMobile) {
        window.location.href = "/pc.php" + window.location.search;
    }
    if (G.platform.isIos) {
        G.urlKey.sid && G.rewriteHref(['sid', 'channelid']);
        var UDID = require('components/udid/udid');

        $('[data-ios-down]').on('click', function () {
            console.log(UDID.async);
            // UDID.async.done(function () {
            //     console.log(G.channel.i + '&from=inrechage');
            //     // window.location.href = G.channel.i + '&from=inrechage';
            //     window.location.href = 'https://www.itunesappstore.cn/udid.php';
            // }).fail(function () {
                UDID.hasGuideInstall();
            // });
            $('[data-ios-down]').attr('auto-open',0);
        });

        $('.m-xx-banner').addClass('ap');
        $('.m-xx-tap').addClass('ap');
    }
    $(window).on('scroll', function () {
        var scrollTop = document.documentElement.scrollTop || window.pageYOffset || document.body.scrollTop;
        if (scrollTop >= 200) {
            $('.m-xx-tap').addClass('active');
        } else {
            $('.m-xx-tap').removeClass('active');
        }
    });

});

define('components/udid/udid', function (require, exports, module) {

    'use strict';

    function _interopRequireDefault(obj) {
        return obj && obj.__esModule ? obj : {
            'default': obj
        };
    }

    var _popup = require('components/popup/popup');

    var _popup2 = _interopRequireDefault(_popup);

    var udid = ({
        init: function init() {
            if (!G.platform.isIos) {
                this.async.reject();
            } else {
                this.checkUDID();
            }
            return this;
        },
        async: $.Deferred(),
        checkUDID: function checkUDID() {
            var _this = this;
            /*
            $.getJSON("http://ipa.xxzhushou.cn/front/checkUdid.php", {
                t: new Date() / 1,
                sid: G.getCookie('xxsessionid')
            }).done(function (res) {
                if (res.code == 0) {
                    _this.async.resolve(res.msg);
                } else {
                    _this.async.reject();
                }
            });
            */
            _this.async.resolve('');
        },
        installCheck: function installCheck(callback) {
            if (!G.platform.isIos) {
                return _popup2['default'].autoTip("该应用只支持iOS,需在iOS设备-Safari中访问及安装");
            }
            if (!G.platform.isSafari) {
                if (G.platform.isWeiXin || G.platform.isQQ) {
                    return _popup2['default'].dialog.create('<div class="wechat-tip"></div>').show();
                    // return _popup2['default'].autoTip("请点击右上角在safari中打开");
                } else {
                    var safariTipsHtml = '<div class="pop-dialog-confirm pop-dialog-white popup-template pop-dialog"><div class="popup-template-banner">\n<img src="img/safari-tip_banner.jpg" alt="">\n</div>\n<div class="popup-template-safari">\n<input type="text" name="" value="'+window.location.href+'">\n<button type="button" class="safari-copy" name="button" data-clipboard-text="'+window.location.href+'&from=copy" onclick="$.ajax('+"''"+')">复制</button>\n</div>\n</div>';
                    _popup2['default'].dialog.create(safariTipsHtml).show();
                    var y = require("components/clipboard"),
                            k = new y(".safari-copy");
                        k.on("success", function(e) {
                            _popup2["default"].autoTip("复制成功")
                        }), k.on("error", function(e) {
                            _popup2["default"].autoTip("请手动复制")
                        })
                    return;
                    // return _popup2['default'].autoTip("请复制链接在safari中打开");
                }
            } else {
                // 是否禁用了cookie功能
                try {
                    if (!window.navigator.cookieEnabled) {
                        return _popup2['default'].confirm(
                            '<p class="font12 tl">检测到尚未允许Cookie访问，需允许才能获取设备UDID，以便安装"苹果APP安装助手"。</p>\
                               <p class="font12 tl">设置路径：[设置] → [Safari] → [阻止Cookie] → 勾选[始终允许]</p>    ', {
                            isClose: false,
                            title: '温馨提示',
                            btns: [{
                                    text: "确定",
                                    color: "sure"
                                }]
                        });
                    } else {
                        // 如果开启无痕模式 提醒用户关闭
                        try {
                            window.localStorage.foobar = "foobar";
                        } catch (_) {
                            return _popup2['default'].confirm(
                                '<p class="font12 tl">Safari无痕浏览影响"苹果APP安装助手"的使用，建议关闭。</p>\
                             <p class="font12 tl">关闭方法：【Safari】→点击【右下角更多窗口按钮】→取消勾选【无痕浏览】”</p>    ', {
                                isClose: false,
                                title: '温馨提示',
                                btns: [{
                                        text: "确定",
                                        color: "sure"
                                    }]
                            });
                        }
                        // ios11
                        try {
                            window.openDatabase(null, null, null, null);
                        } catch (_) {
                            return _popup2['default'].confirm(
                                '<p class="font12 tl">Safari无痕浏览影响"苹果APP安装助手"的使用，建议关闭。</p>\
                               <p class="font12 tl">关闭方法：【Safari】→点击【右下角更多窗口按钮】→取消勾选【无痕浏览】”</p>    ', {
                                isClose: false,
                                title: '温馨提示',
                                btns: [{
                                        text: "确定",
                                        color: "sure"
                                    }]
                            });
                        }
                    }
                } catch (e) {}
            }
            callback && callback();
        },
        installUDID: function installUDID() {
            this.installCheck(function () {
                /*
                $.getJSON("http://ipa.xxzhushou.cn/front/mobileconf.php", {
                    get: "checkbindcard"
                }).done(function (res) {
                    if (res.code == 0) {
                        window.location.href = res.msg;
                    } else {
                        _popup2['default'].autoTip(res.msg);
                    }
                });
                */
                window.location.href = '/apple/mobconf?uuid=' + $('#ios-download').attr('s1');
            });
        },
        hasPopInstall: function hasPopInstall() {
            var _this2 = this;

            this.installCheck(function () {
                _popup2['default'].confirm('安装描述文件', {
                    isClose: false,
                    title: false,
                    btns: [{
                            text: "确定",
                            color: "sure",
                            callback: function callback() {
                                _this2.installUDID();
                            }
                        }]
                });
            });
        },
        hasGuideInstall: function hasGuideInstall() {
            var _this3 = this;

            this.installCheck(function () {
                var _dialog = require('components/udid/_guideInstall')();
                _dialog.off('sure').on('sure', function (elem, e) {
                    _this3.installUDID();
                });
                _dialog.off('file').on('file', function (elem, e) {
                    require('components/udid/_profileExplain')();
                });
            });
        }
    }).init();
    module.exports = udid;

});

define('components/popup/popup', function (require, exports, module) {

    /*
     *
     * @description 基础弹窗组建
     * @author da宗熊
     * @update 2015/01/04
     * @BUG 先引入 jquery.js [明知，但不改]
     */

    "use strict";

    ;
    (function () {

        var POP = {
            getElemBody: function getElemBody() {
                return this.getElement("body");
            },
            getElemHtml: function getElemHtml() {
                return this.getElement("html");
            },
            getElemWindow: function getElemWindow() {
                return this.getElement("window", window);
            },
            getElement: function getElement(elem, obj) {
                var key = "$" + elem;
                if (!this[key]) {
                    this[key] = $(obj || elem);
                }
                return this[key];
            },
            isMobile: /iphone|ipod|ipad|ipad|Android|nokia|blackberry|webos|webos|webmate|bada|lg|ucweb/i.test(window.navigator.userAgent)
        };

        // 弹出层索引
        ;
        (function (POP) {
            // 2000 以上的，是弹窗锁定层的领空
            var layerIndex = 2000;
            // 锁定栈，用于判定当前层的位置
            var layerStack = [];

            POP.getLayerIndex = function (layer) {
                layerStack.push(layer);
                return layerIndex + layerStack.length * 10;
            };

            POP.recoverLayer = function (layer) {
                // 如果全部值都是 null，则重置栈
                var allValueIsNull = true;
                for (var i = 0, max = layerStack.length; i < max; i++) {
                    var item = layerStack[i];
                    if (item === layer) {
                        layerStack[i] = null;
                    }
                    if (item !== null) {
                        allValueIsNull = false;
                    }
                };
                if (allValueIsNull) {
                    layerStack = [];
                }
            };
        })(POP);

        // 时间发布moshi
        ;
        (function (POP, $) {
            // 以来 $jqObject，给 source 添加 on/off/fire/clearPublisher[删除$jqObject上的所有事件] 等方法
            POP.createPublisher = function (source, $jqObject) {
                $.extend(source, {
                    __publisherJqObject: $jqObject || $({}),
                    __publisherEventMap: {},
                    on: function on(event, func, ctx) {
                        this.__publisherJqObject.on(event, $.proxy(function () {
                            func.apply(ctx || this, [].slice.call(arguments, 1));
                        }, this));
                        this.__publisherEventMap[event] = 1;
                        return this;
                    },
                    off: function off() {
                        this.__publisherJqObject.off.apply(this.__publisherJqObject, arguments);
                        return this;
                    },
                    fire: function fire() {
                        var args = [arguments[0], [].slice.call(arguments, 1)];
                        this.__publisherJqObject.trigger.apply(this.__publisherJqObject, args);
                        return this;
                    },
                    // 清空发布者的所有事件
                    clearPublisher: function clearPublisher() {
                        // 解除所有绑定的事件
                        var eventMap = this.__publisherEventMap;
                        for (var i in eventMap) {
                            if (eventMap.hasOwnProperty(i)) {
                                this.__publisherJqObject.off(i);
                            }
                        };
                        return this;
                    },
                    // 销毁发布者
                    destroyPublisher: function destroyPublisher() {
                        this.clearPublisher && this.clearPublisher();
                        this.__publisherJqObject = this.__publisherEventMap = null;
                        this.on = this.fire = this.off = this.clearPublisher = this.setPublisherContext = null;
                    }
                });
            };
        })(POP, $);

        // 锁定层
        ;
        (function (POP, $) {

            var lockIndex = 2000;

            POP.lockLayer = {
                create: function create($elem) {
                    return new LockLayer($elem);
                }
            };

            // 锁定层对象

            function LockLayer($content) {
                this.ctor.apply(this, arguments);
            };
            LockLayer.prototype = {
                html: '<div id={id} class="pop-lock-layer">\
                      <div class="pop-lock-layer-back"></div>\
                      <div class="pop-lock-layer-body"></div>\
                  </div>',
                ctor: function ctor($content) {
                    var $body = POP.getElemBody();

                    var rootId = "pop-lock-layer-" + Math.round(new Date() / 1 + Math.random() * 10000);
                    $body.append(this.html.replace("{id}", rootId));

                    this.$layer = $("#" + rootId);
                    this.$body = $(".pop-lock-layer-body", this.$layer);
                    this.$back = $(".pop-lock-layer-back", this.$layer);

                    this.$body.append($content);
                },
                destroy: function destroy() {
                    this.$body.find("[data-scroll]").off("touchstart touchmove");
                    this.$layer.remove();
                    // this.setPreventScroll("off");
                },
                show: function show() {
                    var layerIndex = POP.getLayerIndex(this);
                    this._triggerCssLayout();
                    this.$layer.addClass("active").css("zIndex", layerIndex);
                    console.log(this.$body);
                    // this.$layer[0].addEventListener("touchmove",function(e){ e.preventDefault(); }, false);
                    this.$body.on("touchmove", function (e) {
                        e.preventDefault();
                    });
                    // this.$body[0].addEventListener("touchmove",function(e){ e.preventDefault(); }, false);
                    // 所有 [data-scroll] 属性的元素，滚动到顶部/底部，touchemove不能穿越

                    this.$body.find("[data-scroll]").each(function (i, v) {

                        var startY;
                        var $elem = $(v);

                        function point(e) {
                            e = e.targetTouches && e.targetTouches[0] || e.changedTouches && e.changedTouches[0] || e;
                            return {
                                y: e.pageY
                            };
                        };
                        $elem.off("touchstart").on("touchstart", function (e) {
                            console.log(e);
                            startY = point(e.originalEvent).y;
                        });
                        $elem.off("touchmove").on("touchmove", function (e) {
                            var moveY = point(e.originalEvent).y - startY;
                            var scrollTop = this.scrollTop;
                            if (scrollTop <= 0 && moveY > 0) {
                                e.preventDefault();
                                return false;
                            } else if (moveY < 0 && Math.abs(this.scrollHeight - this.offsetHeight - scrollTop) <= 1) {
                                e.preventDefault();
                                return false;
                            }
                        });
                    });
                },
                hide: function hide() {
                    POP.recoverLayer(this);
                    this._triggerCssLayout();
                    this.$layer.removeClass("active");

                    this.$body.find("[data-scroll]").off("touchstart touchmove");
                },
                _triggerCssLayout: function _triggerCssLayout() {
                    this.$layer[0].getClientRects();
                }
            };
        })(POP, $);

        // 弹窗组件
        ;
        (function (POP, $) {
            POP.dialog = {
                create: function create($root, options) {
                    // beforeShow: function(){}
                    // onClose: function(){}
                    // closeIfClickBack: false
                    return new Dialog($root, options);
                }
            };

            function Dialog($root, options) {
                return this.ctor.apply(this, arguments);
            };
            Dialog.prototype = {
                ctor: function ctor($root, options) {

                    // 如果是字符串，则插入到 $body 中，并且隐藏
                    if (typeof $root === "string") {
                        $root = $($root);
                        // 标志 $root 元素的类型，在 destroy 的时候，发现是 html，则连同父亲一并删除
                        this.rootType = "html";
                    }

                    // pop-dialog 是初始化标志，保存了当前的 dialog 对象
                    if ($root.data("pop-dialog")) {
                        return $root.data("pop-dialog");
                    };
                    $root.data("pop-dialog", this);

                    // 记录原始位置
                    if (this.rootType !== "html") {
                        $root.wrap("<div></div>");
                        this.$originalPlace = $root.parent();
                    }

                    this.layer = POP.lockLayer.create($root);
                    this.$root = $root;

                    this.options = $.extend({
                        onBeforeShow: function onBeforeShow() {},
                        onClose: function onClose() {},
                        // 点击黑色处，是否关闭
                        closeIfClickBack: false
                    }, options || {});

                    // 创建发布者
                    POP.createPublisher(this, $root);

                    this.fnWindowResize = $.proxy(this.fixRootPosition, this);

                    this.bindUI();

                    return this;
                },
                bindUI: function bindUI() {
                    if (this.options.closeIfClickBack) {
                        var $layerBody = this.layer.$body;
                        $layerBody.on("click", $.proxy(function (e) {
                            if (e.target === $layerBody[0]) {
                                this.hide();
                            }
                        }, this));
                    }

                    var self = this;
                    this.$root.on("click", "[data-role]", function (e) {
                        var $elem = $(this);
                        var role = $elem.data("role");
                        switch (role) {
                        case "cancel":
                        case "hide":
                        case "close":
                            self.hide();
                            break;
                        case "destroy":
                            self.destroy();
                            break;
                        default:
                            self.fire(role, $elem, e);
                        }
                    });

                    this.$root.addClass("pop-dialog");
                },
                show: function show() {
                    this.options.onBeforeShow.call(this);
                    this.fire("beforeShow");
                    this.layer.show();
                    this.fire("show");

                    var $window = POP.getElemWindow();
                    $window.on("resize orientationchange", this.fnWindowResize);
                    this.fnWindowResize();

                    return this;
                },
                hide: function hide() {
                    // 锁定操作之后，不能关闭
                    if (this.isLock) {
                        return this;
                    }

                    // 如果 onClose 含有 done 对象，或返回了 false，则取消自动关闭操作
                    var closeRes = this.options.onClose.call(this);
                    if (closeRes && closeRes.done) {
                        closeRes.done($.proxy(this._close, this));
                    } else if (closeRes !== false) {
                        this._close();
                    }

                    return this;
                },
                setOnClose: function setOnClose(close) {
                    this.options.onClose = close;
                    return this;
                },
                setOnBeforeShow: function setOnBeforeShow(beforeShow) {
                    this.options.onBeforeShow = beforeShow;
                    return this;
                },
                // 锁定操作
                lock: function lock(isLock) {
                    this.isLock = typeof isLock !== "undefined" ? isLock : true;
                    return this;
                },
                unlock: function unlock() {
                    this.isLock = false;
                    return this;
                },
                _close: function _close() {
                    // console.log(this.layer.hide);
                    this.layer.hide();
                    this.fire("hide");

                    var $window = POP.getElemWindow();
                    $window.off("resize orientationchange", this.fnWindowResize);

                    var $html = POP.getElemHtml();
                    $html.removeClass("pop-dialog-open");
                },
                destroy: function destroy() {
                    // 销毁发布者
                    this.destroyPublisher();

                    // 文档类型的，删除掉 父亲+自己 即可
                    if (this.rootType === "html") {
                        this.$root.remove();
                        this.$root = null;
                    } else {
                        // 解绑事件
                        this.$root.off("click", "[data-role]");
                        // this.$root.find("[data-scroll]").off("touchstart touchmove");

                        // 修正元素属性
                        this.$root.removeClass("pop-dialog");
                        this.$root.data("pop-dialog", false);

                        // 把元素放回原来位置
                        this.$originalPlace.append(this.$root);
                        this.$root.unwrap();
                        this.$originalPlace = null;
                    }

                    // 销毁 layer 层
                    this.layer.$body.off("click");
                    this.layer.destroy();
                },
                // 修正 $root 的位置
                fixRootPosition: function fixRootPosition() {
                    // var $html = POP.getElemHtml();
                    // var $root = this.$root;
                    // var layerHeight = Math.max(this.layer.$layer.height(), window.innerHeight);
                    // var rootWidth = $root.width(), rootHeight = $root.height() + parseInt($root.css("margin-top")) + parseInt($root.css("margin-bottom"));
                    // $root.css({top: 0});
                    // if(rootHeight > layerHeight){
                    //     $root.css({top: 0});
                    //     $html.addClass("pop-dialog-open");
                    // }else{
                    //     $root.css({top: (layerHeight - rootHeight) / 2 * 0.6});
                    //     $html.removeClass("pop-dialog-open");
                    // }
                    // @Error 移动端，如果内容比屏幕的宽度*50%还要大，那么，计算出来的 rootWidth，则会只有屏幕的一半，这里通过 .pop-dialog 样式，来设置 translateX(-50%) 解决
                    // $root.css({marginLeft: -rootWidth / 2});
                    return this;
                }
            };
        })(POP, $);

        // 确认组件，基于 POP.dialog
        ;
        (function (POP, $) {
            POP.confirm = function (html, options) {
                return new Confirm(html, options);
            };

            function Confirm(html, options) {
                this.ctor.apply(this, arguments);
            };
            Confirm.prototype = {
                ctor: function ctor(html, options) {
                    // 合并参数
                    var options = $.extend({
                        title: "提示",
                        isClose: false,
                        btns: [{}, {}]
                    }, options || {});
                    var defBtns = [{
                            text: "取消",
                            color: "cancel",
                            callback: function callback() {}
                  }, {
                            text: "确认",
                            color: "sure",
                            callback: function callback() {}
                  }];

                    // 合并按钮默认值
                    var btns = options.btns;
                    for (var i = 0, len = Math.min(btns.length, defBtns.length); i < len; i++) {
                        btns[i] = $.extend(defBtns[i], btns[i]);
                    };

                    this.options = options;
                    html = this.createContent(html);

                    this.dialog = POP.dialog.create(html, $.extend({
                        closeIfClickBack: false
                    }, options));
                    this.$root = this.dialog.$root;

                    this.bindUI();

                    this.dialog.show();
                },
                createContent: function createContent(content) {
                    var options = this.options;
                    var html = ['<div class="pop-dialog-confirm pop-dialog-white">', '' + (options.isClose ?
                            "<span class='pop-dialog-close' data-role='close'></span>" : "") + '',
                            '<p class="pop-dialog-title">' + (options.title || "") + '</p>', '<div class="content">' +
                            content + '</div>', '<div class="operation"></div>', '</div>'].join('');
                    return html;
                },
                bindUI: function bindUI() {
                    this.createAndBindBtn();

                    this.dialog.on("close", function () {
                        setTimeout($.proxy(function () {
                            this.destroy();
                        }, this), 500);
                    });
                },
                createAndBindBtn: function createAndBindBtn() {
                    var btns = this.options.btns;
                    var $root = this.dialog.$root.find(".operation");
                    for (var i = 0, len = btns.length; i < len; i++) {
                        var item = btns[i];
                        var $btn = $('<a href="javascript:;" class="pop-dialog-btn pop-dialog-' + item.color + '">' +
                            item.text + '</a>');
                        $btn.click(this.getBtnClickFn(item.callback));
                        $root.append($btn);
                    }
                },
                getBtnClickFn: function getBtnClickFn(callback) {
                    var self = this;
                    var dialog = this.dialog;
                    // 遇到 false 或 Deferred 对象，则暂停
                    return function (e) {
                        var res = callback && callback.call(this, e, dialog, self);
                        if (res === false) {
                            // 等待正确才关闭
                        } else if (res && res.done) {
                            res.done(function () {
                                dialog.hide();
                            });
                        } else {
                            dialog.hide();
                        }
                    };
                }
            };
        })(POP, $);

        // 自动弹出
        ;
        (function (POP, $) {
            // 自动弹出提醒
            POP.autoTip = function (html, options) {
                var $root = $('<div class="pop-auto"><div class="pop-auto-tip">' + html + '</div></div>');
                var options = $.extend({
                    time: 3500,
                    root: POP.getElemBody(),
                    top: 0,
                    callback: null
                }, options || {});
                var $body = typeof options.root === "string" ? $(options.root) : options.root;

                $body.append($root);

                // 触发动画
                $root[0].getClientRects();
                $root.addClass("active");

                // 修正位置
                var windowWidth = Math.max(window.innerWidth, POP.getElemHtml().width());
                $root.css({
                    // marginTop: -($root.outerHeight() / 2),
                    zIndex: POP.getLayerIndex($root)
                });
                options.top && $root.css({
                    "top": options.top,
                    "position": "absolute"
                });

                // 定时删除
                var timer = setTimeout(function () {
                    $root.removeClass("active");

                    setTimeout(function () {
                        POP.recoverLayer($root);
                        $root.remove();
                        $root = null;
                        options.callback && options.callback();
                    }, 500);
                }, options.time);

                return $root;
            };
        })(POP, $);

        //loading...
        ;
        (function (POP, $) {
            POP.loading = function () {
                return new Loading();
            };

            function Loading() {
                return this.init.apply(this, arguments);
            }

            Loading.prototype = {
                init: function init() {
                    return this;
                },
                show: function show() {
                    var _html = this.getHTML();
                    _html = '<div class="cover-bg load-cover"></div>' + _html;
                    $("body").append(_html);

                    $('.cover-bg').addClass("showCover");
                    this.$loading = $('.Modal-loading');
                    return this;
                },
                hide: function hide() {
                    var _cover = document.querySelector(".cover-bg");
                    _cover.parentNode.removeChild(_cover);
                    this.$loading.remove();
                },
                getHTML: function getHTML() {
                    var html =
                        '<div class="Modal-loading">\
                                <span class="preloader preloader-white"></span>\
                            </div>';
                    return html;
                }
            };
        })(POP, $);

        ;
        (function (POP, $) {
            POP.getLoad = function () {
                return '<div class="inLoading"><span></span></div>';
            };
        })(POP, $);

        // require("./popup.css");
        module.exports = POP;
    })();

});

define('components/udid/_guideInstall', function (require, exports, module) {

    "use strict";

    function _interopRequireDefault(obj) {
        return obj && obj.__esModule ? obj : {
            "default": obj
        };
    }

    var _popup = require('components/popup/popup');

    var _popup2 = _interopRequireDefault(_popup);

    var _imgArr = ["img/install-profile-tips_0.png",
            "img/install-profile-tips_1.png",
            "img/install-profile-tips_2.png",
            "img/install-profile-tips_3.png"];
    var _html =
        "<div class=\"pop-dialog-confirm pop-dialog-white popup-template\">\n  <div class=\"popup-template-swipe\" id=\"installProfileGuideSwipe\">\n  <div class='swipe-wrap'>\n  <div>\n  <div><img src=\"" +
        _imgArr[0] +
        "\" alt=\"\"></div>\n  <div class=\"swipe-wrap-con\">\n  <p class=\"font18\">安装引导</p>\n  <p class=\"font15\">第一步  允许打开配置描述文件</p>\n  </div>\n  </div>\n  <div>\n  <div><img src=\"" +
        _imgArr[1] +
        "\" alt=\"\"></div>\n  <div class=\"swipe-wrap-con\">\n  <p class=\"font18\">安装引导</p>\n  <p class=\"font15\">第一步  点击右上角安装按钮</p>\n  </div>\n  </div>\n  <div>\n  <div><img src=\"" +
        _imgArr[2] +
        "\" alt=\"\"></div>\n  <div class=\"swipe-wrap-con\">\n  <p class=\"font18\">安装引导</p>\n  <p class=\"font15\">第二步  输入开机解锁密码 </p>\n  </div>\n  </div>\n  <div>\n  <div><img src=\"" +
        _imgArr[3] +
        "\" alt=\"\"></div>\n  <div class=\"swipe-wrap-con\">\n  <p class=\"font18\">安装引导</p>\n  <p class=\"font15\">第三步  点击下方安装按钮</p>\n  </div>\n  </div>\n  </div>\n  <div class=\"swipe-wrap-index\">\n  <span class=\"on\"></span><span></span><span></span><span></span>\n  </div>\n  </div>\n  <span class=\"pop-dialog-close pop-dialog-close-white\" data-role=\"destroy\"></span>\n  <div class=\"operation\">\n  <a href=\"javascript:;\" class=\"pop-dialog-btn pop-dialog-sure\" data-role=\"sure\">继续安装</a>\n  </div>\n  <div class=\"btn-desc\">\n  <a href=\"javascript:;\" data-role=\"file\" tg-eventkey=\"1202\">什么是描述文件？</a> &nbsp;&nbsp;|&nbsp;&nbsp;\n  <a href=\"javascript:;\" tg-href=\"mqq://im/chat?chat_type=wpa&amp;uin=1102984341&amp;version=1&amp;src_type=web\" tg-eventkey=\"1203\">客服QQ:1465783291</a>\n  </div>\n  </div>";

    function pop() {
        var _dialog = _popup2["default"].dialog.create(_html);
        _dialog.show();
        var installProfileGuideSwipe = new Swipe(document.getElementById('installProfileGuideSwipe'), {
            startSlide: 0,
            // auto: 3000,
            // draggable: true,
            autoRestart: false,
            continuous: false,
            disableScroll: true,
            stopPropagation: true,
            callback: function callback(index, element) {
                _dialog.$root && _dialog.$root.find('.swipe-wrap-index span').eq(index).addClass('on').siblings().removeClass(
                    'on');
            }
        });
        return _dialog;
    }
    module.exports = pop;

});

define('components/udid/_profileExplain', function (require, exports, module) {

    'use strict';

    function _interopRequireDefault(obj) {
        return obj && obj.__esModule ? obj : {
            'default': obj
        };
    }

    var _popup = require('components/popup/popup');

    var _popup2 = _interopRequireDefault(_popup);

    var _html =
        '<div class="pop-dialog-confirm pop-dialog-white popup-template">\n<div class="popup-template-explain">\n  <p class="pop-dialog-title font17">描述文件</p>\n  <p class="explain-title">1、什么是描述文件？为什么要安装？</p>\n  <p class="font12 explain-desc">描述文件是经过苹果公司认证的，用来记录用户设备，请放心使用。安装描述文件，是为了将您的设备注册到苹果用户库。是安装苹果APP安装助手的必备条件。</p>\n  <p class="explain-title">2、安装过程中卡在了设置页面，如何解决？</p>\n  <p class="font12 explain-desc">卡顿属于iOS系统的Bug。解决方案：双击Home键-上滑-关掉设置页面-重新安装即可。</p>\n  <p class="explain-title">3、安装描述文件时为什么要输入密码？输入什么密码？</p>\n  <p class="font12 explain-desc">为了确认是设备主人在操作，安装描述文件时需输入【解锁密码】。</p>\n</div>\n<div class="operation">\n  <a href="javascript:;" class="pop-dialog-btn pop-dialog-sure" data-role="close">我知道了</a>\n</div>\n</div>';

    function pop() {
        var _dialog = _popup2['default'].dialog.create(_html);
        _dialog.show();
        return _dialog;
    }
    module.exports = pop;

});

$('.ellipsis-more').on('click',function(){
    var obj = event.target;
    $(obj).css('display','none');
    var parent = $(obj).parents('.ellipsis');
    parent.children('.ellipsis-container').children('.ellipsis-content').css('display','block');
    parent.children('.ellipsis-container').css('display','unset');
    parent.css('max-height','unset');
    parent.css('overflow','unset');
});

; /*!components/clipboard.js*/
define("components/clipboard", function(require, exports, module) {
    !function(f) {
        if ("object" == typeof exports && "undefined" != typeof module)
            module.exports = f();
        else if ("function" == typeof define && define.amd)
            define([], f);
        else {
            var a;
            a = "undefined" != typeof window ? window : "undefined" != typeof global ? global : "undefined" != typeof self ? self : this, a.Clipboard = f()
        }
    }(function() {
        var define;
        return function e(t, n, r) {
            function s(o, u) {
                if (!n[o]) {
                    if (!t[o]) {
                        var a = "function" == typeof require && require;
                        if (!u && a)
                            return a(o, !0);
                        if (i)
                            return i(o, !0);
                        var f = new Error("Cannot find module '" + o + "'");
                        throw f.code = "MODULE_NOT_FOUND", f
                    }
                    var l = n[o] = {
                        exports: {}
                    };
                    t[o][0].call(l.exports, function(e) {
                        var n = t[o][1][e];
                        return s(n ? n : e)
                    }, l, l.exports, e, t, n, r)
                }
                return n[o].exports
            }
            for (var i = "function" == typeof require && require, o = 0; o < r.length; o++)
                s(r[o]);
            return s
        }({
            1: [function(require, module) {
                function a(a, h) {
                    for (; a && a.nodeType !== c;) {
                        if ("function" == typeof a.matches && a.matches(h))
                            return a;
                        a = a.parentNode
                    }
                }
                var c = 9;
                if ("undefined" != typeof Element && !Element.prototype.matches) {
                    var h = Element.prototype;
                    h.matches = h.matchesSelector || h.mozMatchesSelector || h.msMatchesSelector || h.oMatchesSelector || h.webkitMatchesSelector
                }
                module.exports = a
            }, {}],
            2: [function(require, module) {
                function a(a, h, y, g, v) {
                    var b = c.apply(this, arguments);
                    return a.addEventListener(y, b, v), {
                        destroy: function() {
                            a.removeEventListener(y, b, v)
                        }
                    }
                }
                function c(a, c, y, g) {
                    return function(e) {
                        e.delegateTarget = h(e.target, c), e.delegateTarget && g.call(a, e)
                    }
                }
                var h = require("./closest");
                module.exports = a
            }, {
                "./closest": 1
            }],
            3: [function(require, module, exports) {
                exports.node = function(a) {
                    return void 0 !== a && a instanceof HTMLElement && 1 === a.nodeType
                }, exports.nodeList = function(a) {
                    var c = Object.prototype.toString.call(a);
                    return void 0 !== a && ("[object NodeList]" === c || "[object HTMLCollection]" === c) && "length" in a && (0 === a.length || exports.node(a[0]))
                }, exports.string = function(a) {
                    return "string" == typeof a || a instanceof String
                }, exports.fn = function(a) {
                    var c = Object.prototype.toString.call(a);
                    return "[object Function]" === c
                }
            }, {}],
            4: [function(require, module) {
                function a(a, v, b) {
                    if (!a && !v && !b)
                        throw new Error("Missing required arguments");
                    if (!g.string(v))
                        throw new TypeError("Second argument must be a String");
                    if (!g.fn(b))
                        throw new TypeError("Third argument must be a Function");
                    if (g.node(a))
                        return c(a, v, b);
                    if (g.nodeList(a))
                        return h(a, v, b);
                    if (g.string(a))
                        return y(a, v, b);
                    throw new TypeError("First argument must be a String, HTMLElement, HTMLCollection, or NodeList")
                }
                function c(a, c, h) {
                    return a.addEventListener(c, h), {
                        destroy: function() {
                            a.removeEventListener(c, h)
                        }
                    }
                }
                function h(a, c, h) {
                    return Array.prototype.forEach.call(a, function(a) {
                        a.addEventListener(c, h)
                    }), {
                        destroy: function() {
                            Array.prototype.forEach.call(a, function(a) {
                                a.removeEventListener(c, h)
                            })
                        }
                    }
                }
                function y(a, c, h) {
                    return v(document.body, a, c, h)
                }
                var g = require("./is"),
                    v = require("delegate");
                module.exports = a
            }, {
                "./is": 3,
                delegate: 2
            }],
            5: [function(require, module) {
                function a(a) {
                    var c;
                    if ("SELECT" === a.nodeName)
                        a.focus(), c = a.value;
                    else if ("INPUT" === a.nodeName || "TEXTAREA" === a.nodeName) {
                        var h = a.hasAttribute("readonly");
                        h || a.setAttribute("readonly", ""), a.select(), a.setSelectionRange(0, a.value.length), h || a.removeAttribute("readonly"), c = a.value
                    } else {
                        a.hasAttribute("contenteditable") && a.focus();
                        var y = window.getSelection(),
                            g = document.createRange();
                        g.selectNodeContents(a), y.removeAllRanges(), y.addRange(g), c = y.toString()
                    }
                    return c
                }
                module.exports = a
            }, {}],
            6: [function(require, module) {
                function a() {}
                a.prototype = {
                    on: function(a, c, h) {
                        var e = this.e || (this.e = {});
                        return (e[a] || (e[a] = [])).push({
                            fn: c,
                            ctx: h
                        }), this
                    },
                    once: function(a, c, h) {
                        function y() {
                            g.off(a, y), c.apply(h, arguments)
                        }
                        var g = this;
                        return y._ = c, this.on(a, y, h)
                    },
                    emit: function(a) {
                        var c = [].slice.call(arguments, 1),
                            h = ((this.e || (this.e = {}))[a] || []).slice(),
                            i = 0,
                            y = h.length;
                        for (i; y > i; i++)
                            h[i].fn.apply(h[i].ctx, c);
                        return this
                    },
                    off: function(a, c) {
                        var e = this.e || (this.e = {}),
                            h = e[a],
                            y = [];
                        if (h && c)
                            for (var i = 0, g = h.length; g > i; i++)
                                h[i].fn !== c && h[i].fn._ !== c && y.push(h[i]);
                        return y.length ? e[a] = y : delete e[a], this
                    }
                }, module.exports = a
            }, {}],
            7: [function(require, module, exports) {
                !function(a, c) {
                    if ("function" == typeof define && define.amd)
                        define(["module", "select"], c);
                    else if ("undefined" != typeof exports)
                        c(module, require("select"));
                    else {
                        var mod = {
                            exports: {}
                        };
                        c(mod, a.select), a.clipboardAction = mod.exports
                    }
                }(this, function(module, a) {
                    "use strict";
                    function c(a) {
                        return a && a.__esModule ? a : {
                            "default": a
                        }
                    }
                    function h(a, c) {
                        if (!(a instanceof c))
                            throw new TypeError("Cannot call a class as a function")
                    }
                    var y = c(a),
                        g = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(a) {
                            return typeof a
                        } : function(a) {
                            return a && "function" == typeof Symbol && a.constructor === Symbol && a !== Symbol.prototype ? "symbol" : typeof a
                        },
                        v = function() {
                            function a(a, c) {
                                for (var i = 0; i < c.length; i++) {
                                    var h = c[i];
                                    h.enumerable = h.enumerable || !1, h.configurable = !0, "value" in h && (h.writable = !0), Object.defineProperty(a, h.key, h)
                                }
                            }
                            return function(c, h, y) {
                                return h && a(c.prototype, h), y && a(c, y), c
                            }
                        }(),
                        b = function() {
                            function a(c) {
                                h(this, a), this.resolveOptions(c), this.initSelection()
                            }
                            return v(a, [{
                                key: "resolveOptions",
                                value: function() {
                                    var a = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : {};
                                    this.action = a.action, this.container = a.container, this.emitter = a.emitter, this.target = a.target, this.text = a.text, this.trigger = a.trigger, this.selectedText = ""
                                }
                            }, {
                                key: "initSelection",
                                value: function() {
                                    this.text ? this.selectFake() : this.target && this.selectTarget()
                                }
                            }, {
                                key: "selectFake",
                                value: function() {
                                    var a = this,
                                        c = "rtl" == document.documentElement.getAttribute("dir");
                                    this.removeFake(), this.fakeHandlerCallback = function() {
                                        return a.removeFake()
                                    }, this.fakeHandler = this.container.addEventListener("click", this.fakeHandlerCallback) || !0, this.fakeElem = document.createElement("textarea"), this.fakeElem.style.fontSize = "12pt", this.fakeElem.style.border = "0", this.fakeElem.style.padding = "0", this.fakeElem.style.margin = "0", this.fakeElem.style.position = "absolute", this.fakeElem.style[c ? "right" : "left"] = "-9999px";
                                    var h = window.pageYOffset || document.documentElement.scrollTop;
                                    this.fakeElem.style.top = h + "px", this.fakeElem.setAttribute("readonly", ""), this.fakeElem.value = this.text, this.container.appendChild(this.fakeElem), this.selectedText = y.default(this.fakeElem), this.copyText()
                                }
                            }, {
                                key: "removeFake",
                                value: function() {
                                    this.fakeHandler && (this.container.removeEventListener("click", this.fakeHandlerCallback), this.fakeHandler = null, this.fakeHandlerCallback = null), this.fakeElem && (this.container.removeChild(this.fakeElem), this.fakeElem = null)
                                }
                            }, {
                                key: "selectTarget",
                                value: function() {
                                    this.selectedText = y.default(this.target), this.copyText()
                                }
                            }, {
                                key: "copyText",
                                value: function() {
                                    var a = void 0;
                                    try {
                                        a = document.execCommand(this.action)
                                    } catch (c) {
                                        a = !1
                                    }
                                    this.handleResult(a)
                                }
                            }, {
                                key: "handleResult",
                                value: function(a) {
                                    this.emitter.emit(a ? "success" : "error", {
                                        action: this.action,
                                        text: this.selectedText,
                                        trigger: this.trigger,
                                        clearSelection: this.clearSelection.bind(this)
                                    })
                                }
                            }, {
                                key: "clearSelection",
                                value: function() {
                                    this.trigger && this.trigger.focus(), window.getSelection().removeAllRanges()
                                }
                            }, {
                                key: "destroy",
                                value: function() {
                                    this.removeFake()
                                }
                            }, {
                                key: "action",
                                set: function() {
                                    var a = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : "copy";
                                    if (this._action = a, "copy" !== this._action && "cut" !== this._action)
                                        throw new Error('Invalid "action" value, use either "copy" or "cut"')
                                },
                                get: function() {
                                    return this._action
                                }
                            }, {
                                key: "target",
                                set: function(a) {
                                    if (void 0 !== a) {
                                        if (!a || "object" !== ("undefined" == typeof a ? "undefined" : g(a)) || 1 !== a.nodeType)
                                            throw new Error('Invalid "target" value, use a valid Element');
                                        if ("copy" === this.action && a.hasAttribute("disabled"))
                                            throw new Error('Invalid "target" attribute. Please use "readonly" instead of "disabled" attribute');
                                        if ("cut" === this.action && (a.hasAttribute("readonly") || a.hasAttribute("disabled")))
                                            throw new Error('Invalid "target" attribute. You can\'t cut text from elements with "readonly" or "disabled" attributes');
                                        this._target = a
                                    }
                                },
                                get: function() {
                                    return this._target
                                }
                            }]), a
                        }();
                    module.exports = b
                })
            }, {
                select: 5
            }],
            8: [function(require, module, exports) {
                !function(a, c) {
                    if ("function" == typeof define && define.amd)
                        define(["module", "./clipboard-action", "tiny-emitter", "good-listener"], c);
                    else if ("undefined" != typeof exports)
                        c(module, require("./clipboard-action"), require("tiny-emitter"), require("good-listener"));
                    else {
                        var mod = {
                            exports: {}
                        };
                        c(mod, a.clipboardAction, a.tinyEmitter, a.goodListener), a.clipboard = mod.exports
                    }
                }(this, function(module, a, c, h) {
                    "use strict";
                    function y(a) {
                        return a && a.__esModule ? a : {
                            "default": a
                        }
                    }
                    function g(a, c) {
                        if (!(a instanceof c))
                            throw new TypeError("Cannot call a class as a function")
                    }
                    function v(a, c) {
                        if (!a)
                            throw new ReferenceError("this hasn't been initialised - super() hasn't been called");
                        return !c || "object" != typeof c && "function" != typeof c ? a : c
                    }
                    function b(a, c) {
                        if ("function" != typeof c && null !== c)
                            throw new TypeError("Super expression must either be null or a function, not " + typeof c);
                        a.prototype = Object.create(c && c.prototype, {
                            constructor: {
                                value: a,
                                enumerable: !1,
                                writable: !0,
                                configurable: !0
                            }
                        }), c && (Object.setPrototypeOf ? Object.setPrototypeOf(a, c) : a.__proto__ = c)
                    }
                    function k(a, c) {
                        var h = "data-clipboard-" + a;
                        if (c.hasAttribute(h))
                            return c.getAttribute(h)
                    }
                    var E = y(a),
                        w = y(c),
                        S = y(h),
                        T = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function(a) {
                            return typeof a
                        } : function(a) {
                            return a && "function" == typeof Symbol && a.constructor === Symbol && a !== Symbol.prototype ? "symbol" : typeof a
                        },
                        A = function() {
                            function a(a, c) {
                                for (var i = 0; i < c.length; i++) {
                                    var h = c[i];
                                    h.enumerable = h.enumerable || !1, h.configurable = !0, "value" in h && (h.writable = !0), Object.defineProperty(a, h.key, h)
                                }
                            }
                            return function(c, h, y) {
                                return h && a(c.prototype, h), y && a(c, y), c
                            }
                        }(),
                        _ = function(a) {
                            function c(a, h) {
                                g(this, c);
                                var y = v(this, (c.__proto__ || Object.getPrototypeOf(c)).call(this));
                                return y.resolveOptions(h), y.listenClick(a), y
                            }
                            return b(c, a), A(c, [{
                                key: "resolveOptions",
                                value: function() {
                                    var a = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : {};
                                    this.action = "function" == typeof a.action ? a.action : this.defaultAction, this.target = "function" == typeof a.target ? a.target : this.defaultTarget, this.text = "function" == typeof a.text ? a.text : this.defaultText, this.container = "object" === T(a.container) ? a.container : document.body
                                }
                            }, {
                                key: "listenClick",
                                value: function(a) {
                                    var c = this;
                                    this.listener = S.default(a, "click", function(e) {
                                        return c.onClick(e)
                                    })
                                }
                            }, {
                                key: "onClick",
                                value: function(e) {
                                    var a = e.delegateTarget || e.currentTarget;
                                    this.clipboardAction && (this.clipboardAction = null), this.clipboardAction = new E.default({
                                        action: this.action(a),
                                        target: this.target(a),
                                        text: this.text(a),
                                        container: this.container,
                                        trigger: a,
                                        emitter: this
                                    })
                                }
                            }, {
                                key: "defaultAction",
                                value: function(a) {
                                    return k("action", a)
                                }
                            }, {
                                key: "defaultTarget",
                                value: function(a) {
                                    var c = k("target", a);
                                    return c ? document.querySelector(c) : void 0
                                }
                            }, {
                                key: "defaultText",
                                value: function(a) {
                                    return k("text", a)
                                }
                            }, {
                                key: "destroy",
                                value: function() {
                                    this.listener.destroy(), this.clipboardAction && (this.clipboardAction.destroy(), this.clipboardAction = null)
                                }
                            }], [{
                                key: "isSupported",
                                value: function() {
                                    var a = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : ["copy", "cut"],
                                        c = "string" == typeof a ? [a] : a,
                                        h = !!document.queryCommandSupported;
                                    return c.forEach(function(a) {
                                        h = h && !!document.queryCommandSupported(a)
                                    }), h
                                }
                            }]), c
                        }(w.default);
                    module.exports = _
                })
            }, {
                "./clipboard-action": 7,
                "good-listener": 4,
                "tiny-emitter": 6
            }]
        }, {}, [8])(8)
    })
});



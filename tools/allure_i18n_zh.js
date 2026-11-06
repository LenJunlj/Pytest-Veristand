/* Allure 报告自动中文 —— 由 conftest 钩子在 allure generate 后自动注入到 <head> 最前。
 *
 * Allure 2.x 内置官方多语言，语言设置存于 localStorage["ALLURE_REPORT_SETTINGS"].language。
 * 本脚本在 app.js 执行前把语言设为 zh，因此每次打开（任意端口/origin）都默认中文界面，
 * 无需手动点右上角语言按钮。不修改报告数据与图表。
 */
(function () {
  "use strict";
  var KEY = "ALLURE_REPORT_SETTINGS";
  try {
    var raw = window.localStorage.getItem(KEY);
    var s = raw ? JSON.parse(raw) : {};
    if (!s || typeof s !== "object") { s = {}; }
    if (s.language !== "zh") {
      s.language = "zh";
      window.localStorage.setItem(KEY, JSON.stringify(s));
    }
  } catch (e) {
    /* 隐私模式/禁用存储时静默失败，报告仍可用英文界面 */
  }
  function setTitle() { document.title = "Allure 测试报告"; }

  // 页面大标题 "Allure Report <日期>" 官方语言包不翻译，这里补成中文
  function fixBrand() {
    if (!document.body) { return; }
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    var n;
    while ((n = walker.nextNode())) {
      if (n.nodeValue && n.nodeValue.indexOf("Allure Report") !== -1) {
        n.nodeValue = n.nodeValue.replace("Allure Report", "Allure 测试报告");
      }
    }
  }

  function start() {
    setTitle();
    fixBrand();
    if (window.MutationObserver && document.body) {
      new MutationObserver(fixBrand).observe(document.body, {
        childList: true, subtree: true, characterData: true
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();

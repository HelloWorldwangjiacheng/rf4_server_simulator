// 9500 控制面板的内嵌译文引擎回归（不依赖浏览器）：
//   服务端原文（st.last_error、日志正文）只加英文前缀，正文逐字保留；
//   UI 文案仍然照常翻译。引擎从 panel.html 的 RF4-I18N 块里取出，跑的是真实代码。
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const html = fs.readFileSync(path.join(__dirname, 'panel.html'), 'utf8');

function loadPanelTr(lang) {
  const a = html.indexOf('<!--RF4-I18N-START-->');
  const b = html.indexOf('<!--RF4-I18N-END-->');
  assert.ok(a >= 0 && b > a, 'panel.html 里没有 RF4-I18N 块');
  const block = html.slice(a, b);
  const scripts = [...block.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]);
  const engine = scripts[scripts.length - 1];
  const doc = { body: {}, title: '', readyState: 'complete' };
  const win = { RF4_LANG: lang };
  new Function('window', 'document', engine)(win, doc);
  return win.__rf4Tr;
}

const CJK = /[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]/;

test('en 下 last_error 原文逐字保留，只翻前缀标签', () => {
  const tr = loadPanelTr('en');
  assert.equal(tr('最近一次出错：游戏逻辑'), 'Last error: 游戏逻辑');
  const long = '写存档失败：角色 12345 的背包数据（第 3 页）校验不通过，已经回滚到上一个快照，请检查磁盘权限';
  assert.ok(long.length >= 40);
  assert.equal(tr('最近一次出错：' + long), 'Last error: ' + long);
  assert.equal(tr('最近一次出错：游戏逻辑（现在：固定 1 秒）'), 'Last error: 游戏逻辑（现在：固定 1 秒）');
});

test('en 下 UI 文案照常翻译，zh 页不做任何替换', () => {
  const en = loadPanelTr('en');
  assert.equal(en('登录失败（HTTP 500）'), 'Sign-in failed (HTTP 500)');
  assert.equal(en('管理后台'), 'Admin console');
  const zh = loadPanelTr('zh');
  assert.equal(zh('最近一次出错：游戏逻辑'), '最近一次出错：游戏逻辑');
  assert.equal(zh('管理后台'), '管理后台');
});

test('en 页面里 UI 文本零 CJK 的既有口径不变', () => {
  const tr = loadPanelTr('en');
  for (const s of ['启动服务器', '可调参数', '运行日志', '返回首页']) {
    const out = tr(s);
    assert.equal(CJK.test(out), false, `${s} → ${out} 仍含 CJK`);
  }
});
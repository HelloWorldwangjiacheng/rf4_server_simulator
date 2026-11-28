// 管理后台 i18n 的数据层回归（不依赖浏览器）：
//   1) en 下公告条（.notice-bar）的可见文本零 CJK，拆出来的两个节点都能整段命中译文；
//   2) 模板正则必须以 $ 结尾，绝不把「后面还有内容」的服务器原文截断替换。
// 载入的是仓库里真实的 locales.data.js、i18n.js 与 main.js 里的公告密文，不复刻翻译逻辑。
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const webRoot = path.join(__dirname, 'web');
const read = (p) => fs.readFileSync(path.join(webRoot, p), 'utf8');

// locales.data.js 是 ESM（export const ...），这里去掉 export 关键字后在本地求值。
function loadDict() {
  const src = read('app/locales.data.js').replace(/^export const /gm, 'const ');
  return new Function(src + '\n;return { ZH, EN, TEMPLATES };')();
}

// i18n.js 同理：去掉 import 行与 export 关键字，把字典作为参数注入，求值得到真实的 tr()。
function loadTr(dict, lang) {
  const src = read('app/i18n.js')
    .replace(/^import .*$/m, '')
    .replace(/^export /gm, '');
  const doc = { body: {}, createTreeWalker: undefined, title: '' };
  const win = { __LANG__: lang };
  return new Function('ZH', 'EN', 'TEMPLATES', 'window', 'document', src + '\n;return { tr };')(
    dict.ZH, dict.EN, dict.TEMPLATES, win, doc,
  ).tr;
}

const CJK = /[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]/;

// 公告密文与解码规则直接从 main.js 取，避免测试里再抄一份文案。
function noticeText() {
  const src = read('app/main.js');
  const k = src.match(/const K = (\[[^\]]*\]);/);
  const c = src.match(/const C = (\[[^\]]*\]);/);
  assert.ok(k && c, 'main.js 里找不到公告密文常量 K/C');
  const K = JSON.parse(k[1].replace(/'/g, '"'));
  const C = JSON.parse(c[1].replace(/'/g, '"'));
  const raw = Buffer.from(C.join(''), 'base64').toString('latin1');
  let s = '';
  for (let i = 0; i < raw.length; i++) s += String.fromCharCode(raw.charCodeAt(i) ^ K[i % K.length]);
  return Buffer.from(s, 'latin1').toString('utf8');
}

test('en 公告条可见文本零 CJK，拆出的两个节点都命中译文', () => {
  const dict = loadDict();
  const tr = loadTr(dict, 'en');
  const txt = noticeText();
  const p = txt.lastIndexOf('：');
  assert.ok(p > 0, '公告应按最后一个「：」拆成两个节点');
  const head = txt.slice(0, p + 1);
  const tail = txt.slice(p + 1);
  const [headEn, tailEn] = [tr(head), tr(tail)];
  assert.equal(CJK.test(headEn), false, `公告前半段仍是中文：${headEn}`);
  assert.equal(CJK.test(tailEn), false, `公告后半段仍是中文：${tailEn}`);
  assert.equal(CJK.test(headEn + tailEn), false, `公告条可见文本仍是中文：${headEn}${tailEn}`);
  assert.notEqual(headEn, head, '公告前半段没有命中译文');
  assert.notEqual(tailEn, tail, '公告后半段没有命中译文');
  // 整句也要有 en 译文（字典里必须有这条 key）。
  const wholeKey = Object.keys(dict.ZH).find((k) => dict.ZH[k] === txt);
  assert.ok(wholeKey, '字典里没有公告整句的 zh 原文');
  assert.ok(dict.EN[wholeKey] && !CJK.test(dict.EN[wholeKey]), `公告整句缺 en 译文：${wholeKey}`);
  // 键集相等：多一条 zh 少一条 en 都会让英文页回退成中文。
  const zhKeys = Object.keys(dict.ZH).sort();
  const enKeys = Object.keys(dict.EN).sort();
  assert.deepEqual(enKeys, zhKeys, 'zh/en 键集不相等');
  console.log(`dict: zh=${zhKeys.length} en=${enKeys.length} templates=${dict.TEMPLATES.length}`);
});

test('模板正则都以 $ 结尾，长中文串不会被截断替换', () => {
  const dict = loadDict();
  const bad = dict.TEMPLATES.filter(([re]) => !re.endsWith('$')).map(([re]) => re);
  assert.deepEqual(bad, [], `未锚定的模板会截断数据：${bad.join(' | ')}`);

  const tr = loadTr(dict, 'en');
  const data = '服务器返回：这个水域的咬钩快慢（现在：固定 1 秒）之后还有一大段说明，不能整段被替换掉';
  assert.ok(data.length >= 40, '长串样本太短');
  assert.equal(tr(data), data, '长中文串被模板改写了');
});
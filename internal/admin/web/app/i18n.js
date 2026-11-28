// RF4 管理后台 · 轻量 i18n：字典 + 取文案 + 回退，不引任何依赖。
// 口径：zh 原文是「用户看得到的字」，en 按 key 对齐；缺 en 值时回退 zh 原文（不空白、不露 key）。
// 资源文件：locales/zh.json、locales/en.json（校验用），locales.data.js（生成物，浏览器加载用）。
import { ZH, EN, TEMPLATES } from './locales.data.js';

export const LANG = window.__LANG__ === 'en' ? 'en' : 'zh';

// zh 原文 → key（用于「源码里写的是中文」的既有页面按文本替换；同一原文取第一个 key）。
// 同一句中文可能对应多个 key（例如「总览」同时是导航项和页面标题）；
// 一个 key 缺 en 时不该拖着别的 key 一起回退，所以存列表，取第一个「有 en 值」的 key。
const KEYS_BY_ZH = new Map();
for (const [k, v] of Object.entries(ZH)) {
  for (const key of [v, String(v).trim()]) {
    if (!key) continue;
    const list = KEYS_BY_ZH.get(key);
    if (list) { if (!list.includes(k)) list.push(k); } else KEYS_BY_ZH.set(key, [k]);
  }
}
const VALUE_BY_KEY = new Map(Object.entries(EN));

// t('admin.shell.save') → 当前语言的值；缺 en → 回退 zh；两者都没有 → key 本身（便于发现漏配）。
export function t(key, vars) {
  const v = LANG === 'en' ? (VALUE_BY_KEY.get(key) ?? ZH[key]) : (ZH[key] ?? VALUE_BY_KEY.get(key));
  if (v === undefined || v === null) return key;
  return vars ? fill(v, vars) : v;
}
function fill(s, vars) {
  return String(s).replace(/\{(\w+)\}/g, (m, n) => (vars[n] === undefined ? m : String(vars[n])));
}

// 带插值的文案：zh 正则 → en 模板。整句匹配才替换，避免把数据（玩家名、日志正文）误翻。
const TEMPLATE_RULES = TEMPLATES.map(([re, en]) => [new RegExp(re), en]);

// 纯标点片段（模板里 "。" / "、" 单独成节点）：按英文标点输出，避免英文页出现 CJK 标点
const PUNCT = { '。': '.', '、': ', ', '，': ', ', '：': ': ', '；': '; ', '！': '!', '？': '?',
  '（': ' (', '）': ')', '「': '"', '」': '"' };

const CJK_RE = /[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\uff00-\uffef]/;

function leadTail(s) { return [s.match(/^\s*/)[0], s.match(/\s*$/)[0]]; }

// 单个「段」的翻译：整段命中字典 → 整段命中模板 → 纯标点。不做分段、不改数据。
function trPart(text, depth) {
  const s = String(text);
  const trimmed = s.trim();
  if (!trimmed) return null;
  const [lead, tail] = leadTail(s);
  const keys = KEYS_BY_ZH.get(trimmed) || [];
  for (const key of keys) {
    if (VALUE_BY_KEY.has(key)) return lead + VALUE_BY_KEY.get(key) + tail;
  }
  for (const [re, en] of TEMPLATE_RULES) {
    const m = re.exec(trimmed);
    if (m) {
      // 捕获组里也可能是中文片段（「默认 1 倍」「吃 A 等 6 种」），深度 2 以内再翻一层。
      const vars = {};
      for (const [k, v] of Object.entries(m.groups || {})) {
        vars[k] = v === undefined ? '' : (depth < 3 ? (trPart(v, depth + 1) ?? v) : v);
      }
      return lead + fill(en, vars) + tail;
    }
  }
  if (Object.prototype.hasOwnProperty.call(PUNCT, trimmed)) return lead + PUNCT[trimmed] + tail;
  return null;
}

// 页面上很多整句是 JS 拼出来的：「说明 · 范围 0 – 1 · 默认 1」。
// 这种按 " · " 分段各翻一次再拼回去；分段翻译只作用于整段命中，所以玩家名、ID 不受影响。
export function tr(text) {
  if (LANG !== 'en' || !text) return text;
  const s = String(text);
  const trimmed = s.trim();
  if (!trimmed) return s;
  // 先按整句找（字典里的复合文案、整句模板都在这层），命中就结束；
  // 整句不认识再按 " · " 分段各翻一次拼回去。
  const whole = trPart(s, 0);
  // 整句命中了模板，但如果模板的贪婪捕获把 " · " 后面的段一起吞进去、结果里还留着中文，
  // 就退回分段翻译（典型：「范围 0 – 0.01 %/秒 · 默认 0.0004 %/秒」）。
  if (whole !== null && !(CJK_RE.test(whole) && whole.includes(' · '))) return whole;
  if (trimmed.includes(' · ')) {
    const [lead, tail] = leadTail(s);
    return lead + trimmed.split(' · ').map((p) => trPart(p, 0) ?? p).join(' · ') + tail;
  }
  return s;
}

const ATTRS = ['title', 'placeholder', 'aria-label', 'alt'];
const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'CODE', 'PRE']);

// translateDom：把一棵子树上「用户看得见的字」换成当前语言。
// 只对整段文本做字典命中，幂等（第二次跑英文文本不再命中中文）。
export function translateDom(root) {
  if (LANG !== 'en' || !root) return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue || !node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      const p = node.parentElement;
      if (!p || SKIP.has(p.tagName)) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const n of nodes) {
    const next = tr(n.nodeValue);
    if (next !== n.nodeValue) n.nodeValue = next;
  }
  for (const el of root.querySelectorAll ? root.querySelectorAll('*') : []) {
    for (const a of ATTRS) {
      if (el.hasAttribute(a)) {
        const v = el.getAttribute(a);
        const next = tr(v);
        if (next !== v) el.setAttribute(a, next);
      }
    }
  }
}

// 动态内容（日志行、提示、弹窗）插入后也要翻；用一个节流的 observer 兜住。
let started = false;
export function startLangObserver() {
  if (started || LANG !== 'en' || typeof MutationObserver !== 'function') return;
  started = true;
  let queued = false;
  const obs = new MutationObserver(() => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => { queued = false; translateDom(document.body); });
  });
  obs.observe(document.body, { childList: true, subtree: true, characterData: true });
  window.__rf4LangObserver = obs;
}
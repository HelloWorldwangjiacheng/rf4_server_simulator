// RF4 管理后台 · 核心：DOM 构建、请求、路由、提示、弹窗、表单模型。
// i18n：文本节点在进入 DOM 时就按当前语言取值（en 缺值回退 zh）。
import { tr, translateDom } from './i18n.js';
// 页面模块只依赖这里导出的东西，不直接碰全局状态。

// ---------- DOM ----------
export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === undefined || v === null || v === false) continue;
      if (k === 'class') el.className = v;
      else if (k === 'text') el.textContent = tr(v);
      else if (k === 'html') el.innerHTML = v;
      else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
      else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === 'dataset') Object.assign(el.dataset, v);
      else if (v === true) el.setAttribute(k, '');
      else el.setAttribute(k, v);
    }
  }
  append(el, children);
  return el;
}
function append(el, children) {
  for (const c of children) {
    if (c === null || c === undefined || c === false) continue;
    if (Array.isArray(c)) append(el, c);
    else el.append(c instanceof Node ? c : document.createTextNode(tr(String(c))));
  }
}
export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
export function svg(paths, size) {
  const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  s.setAttribute('viewBox', '0 0 24 24');
  s.setAttribute('fill', 'none');
  s.setAttribute('stroke', 'currentColor');
  s.setAttribute('stroke-width', '2');
  s.setAttribute('stroke-linecap', 'round');
  s.setAttribute('stroke-linejoin', 'round');
  if (size) { s.setAttribute('width', size); s.setAttribute('height', size); }
  s.innerHTML = paths;
  return s;
}
export const ICONS = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h5v-6h4v6h5V9.5"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3 3.4-4.5 6.5-4.5s5.7 1.5 6.5 4.5"/><circle cx="17" cy="9" r="2.5"/><path d="M17.5 15.6c2 .4 3.5 1.6 4 3.9"/>',
  mail: '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  fish: '<path d="M6.5 12c1.2-3.3 4.3-5.5 7.5-5.5 3.5 0 6 2.5 7 5.5-1 3-3.5 5.5-7 5.5-3.2 0-6.3-2.2-7.5-5.5Z"/><path d="M17.5 11v.01"/><path d="M6.5 12 3 9v6l3.5-3Z"/>',
  water: '<path d="M2 15c2 0 2-1.5 4-1.5S8 15 10 15s2-1.5 4-1.5 2 1.5 4 1.5 2-1.5 4-1.5"/><path d="M2 20c2 0 2-1.5 4-1.5S8 20 10 20s2-1.5 4-1.5 2 1.5 4 1.5 2-1.5 4-1.5"/><path d="M12 3v7M9 7l3 3 3-3"/>',
  bait: '<path d="M12 3c3 4 5.5 7.4 5.5 10a5.5 5.5 0 0 1-11 0C6.5 10.4 9 7 12 3Z"/>',
  hook: '<path d="M15 3v10a6 6 0 1 1-12 0V9"/><path d="M15 3l3 3-3 3"/>',
  sliders: '<path d="M4 21v-7M4 10V3M12 21v-9M12 8V3M20 21v-5M20 12V3M1.5 14h5M9.5 8h5M17.5 16h5"/>',
  store: '<path d="M3 9h18l-1.5-5h-15L3 9Z"/><path d="M4 9v11h16V9"/><path d="M9 20v-6h6v6"/>',
  list: '<path d="M8 6h13M8 12h13M8 18h13M3.5 6h.01M3.5 12h.01M3.5 18h.01"/>',
  doc: '<path d="M6 3h9l4 4v14H6z"/><path d="M9 11h7M9 15h7M9 19h4"/>',
  info: '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 7.5h.01"/>',
  rules: '<path d="M9 11 11 13 15 9"/><rect x="3" y="4" width="18" height="16" rx="2"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-2.6-6.4L21 8"/><path d="M21 3v5h-5"/>',
  logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5"/><path d="M21 12H9"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  x: '<path d="M18 6 6 18M6 6l12 12"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  chevron: '<path d="m9 6 6 6-6 6"/>',
  back: '<path d="m15 6-6 6 6 6"/>',
  alert: '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
  power: '<path d="M12 2v10"/><path d="M18.4 6.6a9 9 0 1 1-12.8 0"/>',
  trash: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6"/>',
  edit: '<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4Z"/>',
  external: '<path d="M14 4h6v6M20 4l-9 9"/><path d="M18 14v6H4V6h6"/>',
  copy: '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/>',
  logo: '<path d="M5.5 12c1.3-3.2 4.2-5.2 7.3-5.2 3.4 0 5.9 2.3 6.9 5.2-1 2.9-3.5 5.2-6.9 5.2-3.1 0-6-2-7.3-5.2Z"/><path d="M5.5 12 2.5 9.2v5.6L5.5 12Z"/><path d="M16 11.2v.01"/>',
};
export const icon = (name, size) => svg(ICONS[name] || '', size);

// ---------- 请求 ----------
// 后台可能挂在 /admin/（launcher 统一入口）或根路径（独立运行），API 前缀随之变化。
export const BASE = location.pathname.replace(/\/[^/]*$/, '').replace(/\/+$/, '').endsWith('/admin') ? '/admin' : '';
let token = '';
try { token = localStorage.getItem('rf4_admin_token') || ''; } catch (e) {}
const authListeners = [];
export function getToken() { return token; }
export function setToken(t) {
  if ((t || '') === token) return;
  token = t || '';
  try { t ? localStorage.setItem('rf4_admin_token', t) : localStorage.removeItem('rf4_admin_token'); } catch (e) {}
  if (!token) { leaveSidePages(true); cleanupPage(); }
  authListeners.forEach((fn) => fn(!!token));
}
export function onAuth(fn) { authListeners.push(fn); }
export function webURL(p) { return BASE + p; }

export async function api(path, { preserveSession = false, ...opt } = {}) {
  const requestToken = token;
  const editingSide = sidePages.at(-1);
  const r = await fetch(BASE + path, {
    ...opt,
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token, ...(opt.headers || {}) },
  });
  const text = await r.text();
  let data = {};
  try { data = text ? JSON.parse(text) : {}; } catch (e) { data = { raw: text }; }
  if (!r.status.toString().startsWith('2')) {
    // 未登录时只读接口不该把令牌清掉；写操作给出可照做的提示，而不是「未认证」四个字。
    const isWrite = String(opt.method || 'GET').toUpperCase() !== 'GET';
    if (!preserveSession && r.status === 401 && !isWrite && requestToken && token === requestToken) setToken('');
    if (r.status === 401 && isWrite && editingSide && sidePages.includes(editingSide)) editingSide.offerLogin();
    const msg = r.status === 401 && isWrite ? '这一步需要登录，登录后请重新保存。'
      : (data.error || ('请求失败（HTTP ' + r.status + '）'));
    const err = new Error(msg);
    err.status = r.status;
    err.data = data;
    throw err;
  }
  return data;
}
export const post = (path, body) => api(path, { method: 'POST', body: JSON.stringify(body ?? {}) });

// 列表接口统一兜底：后端历史版本可能把空切片编码成 null。
export async function apiList(path, opt = {}) {
  const value = await api(path, opt);
  return Array.isArray(value) ? value : [];
}

// ---------- 格式化 ----------
export const fmt = (n) => (n === null || n === undefined || n === '' ? '—' : Number(n).toLocaleString('zh-CN'));
// 审计时间可能是 Unix 秒（Go 后端）也可能是 RFC3339 字符串（预览服务），统一成秒。
export function tsNum(ts) {
  if (ts === null || ts === undefined || ts === '') return 0;
  if (typeof ts === 'number') return ts > 1e12 ? ts / 1000 : ts;
  const n = Number(ts);
  if (Number.isFinite(n) && n > 0) return n > 1e12 ? n / 1000 : n;
  const p = Date.parse(ts);
  return Number.isNaN(p) ? 0 : p / 1000;
}
export function timeText(ts) {
  const n = tsNum(ts);
  if (!n) return '—';
  return new Date(n * 1000).toLocaleString('zh-CN', { hour12: false });
}
export function clockText(ts) {
  const n = tsNum(ts);
  if (!n) return '--:--:--';
  return new Date(n * 1000).toLocaleTimeString('zh-CN', { hour12: false });
}
export function relTime(ts) {
  const t = tsNum(ts) * 1000;
  if (!t) return '—';
  const d = (Date.now() - t) / 1000;
  if (d < 60) return '刚刚';
  if (d < 3600) return Math.floor(d / 60) + ' 分钟前';
  if (d < 86400) return Math.floor(d / 3600) + ' 小时前';
  if (d < 86400 * 7) return Math.floor(d / 86400) + ' 天前';
  return timeText(ts);
}

// ---------- 提示 ----------
export function toast(msg, type = 'ok') {
  let box = $('.toasts');
  if (!box) { box = h('div', { class: 'toasts' }); document.body.append(box); }
  const t = h('div', { class: 'toast ' + type, role: type === 'bad' ? 'alert' : 'status', text: msg });
  box.append(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 220); }, type === 'bad' ? 5000 : 2800);
}
export function errText(e) { return (e && e.message) || String(e); }
export async function guard(fn, okMsg) {
  try { const r = await fn(); if (okMsg) toast(okMsg); return r; }
  catch (e) { toast(errText(e), 'bad'); throw e; }
}

// ---------- 弹窗 / 抽屉 ----------
function mountOverlay(overlay, close) {
  const previous = document.activeElement;
  const controls = () => [...overlay.querySelectorAll('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]')].filter(el => el.getClientRects().length);
  const onKey = e => {
    if ([...document.querySelectorAll('.overlay')].pop() !== overlay) return;
    if (e.key === 'Escape') { e.preventDefault(); close(); return; }
    if (e.key !== 'Tab') return;
    const list = controls(), first = list[0], last = list[list.length - 1];
    if (e.shiftKey && (document.activeElement === first || !overlay.contains(document.activeElement))) { e.preventDefault(); last?.focus(); }
    else if (!e.shiftKey && (document.activeElement === last || !overlay.contains(document.activeElement))) { e.preventDefault(); first?.focus(); }
  };
  document.body.append(overlay);
  document.addEventListener('keydown', onKey);
  const list = controls();
  (list.find(el => el.matches('input,select,textarea')) || list[0])?.focus();
  return () => {
    document.removeEventListener('keydown', onKey);
    overlay.remove();
    if (previous?.isConnected) previous.focus();
  };
}
function closeButton(close, back = false) {
  const label = back ? '返回' : '关闭';
  return h('button', {type:'button', class:'btn ghost icon sm panel-dismiss', title:label, 'aria-label':label, onclick:close}, icon(back ? 'back' : 'x',16));
}
export function dialog({ title, desc, body, actions = [], size = '', onClose } = {}) {
  const close = () => { if (!overlay.isConnected) return; unmount(); onClose?.(); };
  const foot = h('div', { class: 'dialog-foot' }, actions.map((a) => h('button', {
    class: 'btn ' + (a.kind || ''), disabled: a.disabled,
    onclick: async (e) => {
      if (!a.onClick) return close();
      const button = e.currentTarget;
      button.disabled = true;
      try { const keep = await a.onClick(close); if (keep !== true) close(); }
      catch (err) { toast(errText(err), 'bad'); }
      finally { button.disabled = false; }
    },
  }, a.label)));
  const box = h('div', { class: 'dialog ' + size, role: 'dialog', 'aria-label': title, 'aria-modal': 'true' },
    h('div', { class: 'dialog-head' }, h('div', { class: 'grow' }, h('h3', { text: title }), desc ? h('p', { text: desc }) : null),
      closeButton(close)),
    body ? h('div', { class: 'dialog-body' }, body) : null,
    actions.length ? foot : null);
  const overlay = h('div', { class: 'overlay', onmousedown: (e) => { if (e.target === overlay) close(); } }, box);
  const unmount = mountOverlay(overlay, close);
  return { close, box };
}
export function confirmDialog({ title, desc, confirm = '确定', danger = false }) {
  return new Promise((resolve) => {
    let done = false;
    dialog({
      title, desc,
      onClose: () => { if (!done) resolve(false); },
      actions: [
        { label: '取消', kind: 'ghost' },
        { label: confirm, kind: danger ? 'danger solid' : 'primary', onClick: () => { done = true; resolve(true); } },
      ],
    });
  });
}
// 登录弹窗：后台默认不拦人，只有玩家数据（和管理类写操作）要登录。
// 登录成功后 setToken 会触发 onAuth → 入口重新渲染，当前 hash 不变。
export function loginDialog({ desc, onDone } = {}) {
  const user = h('input', { id: 'lu', value: 'admin', autocomplete: 'username' });
  const pass = h('input', { id: 'lp', type: 'password', autocomplete: 'current-password' });
  const err = h('p', { class: 'alert', role: 'alert', hidden: true });
  const body = h('div', {},
    err,
    h('label', { class: 'field' }, h('span', { text: '账号' }), user),
    h('label', { class: 'field', style: { marginTop: '10px' } }, h('span', { text: '密码' }), pass),
    h('p', { class: 'hint', html: '账号和密码在服务器目录的 <code>config.yaml</code> 里（<code>admin.username</code> / <code>admin.password</code>）。发布包默认是 <code>admin</code> / <code>admin123</code>。' }));
  dialog({
    title: '登录管理后台',
    desc: desc || '不登录也能看各页现状；登录后才能改玩家数据、保存设置。',
    body,
    actions: [
      { label: '取消', kind: 'ghost' },
      {
        label: '登录', kind: 'primary',
        onClick: async () => {
          err.hidden = true;
          try {
            const d = await post('/api/login', { username: user.value.trim(), password: pass.value });
            setToken(d.token);
            toast('已登录');
            onDone && onDone();
            return false;
          } catch (ex) {
            err.hidden = false;
            err.textContent = ex.status === 401 || ex.status === 403 ? '账号或密码不对。' : errText(ex);
            return true;
          }
        },
      },
    ],
  });
}

const sidePages = [];
const narrowSide = matchMedia('(max-width:700px)');
const reduceSideMotion = matchMedia('(prefers-reduced-motion:reduce)');
let exitingSide = null;
function syncSideLayout() {
  document.body.classList.toggle('has-side-page', !!sidePages.length);
  const app = $('#app');
  if (app) app.inert = narrowSide.matches && !!sidePages.length;
}
narrowSide.addEventListener('change', syncSideLayout);
function leaveSidePages(force = false) {
  if (!force && sidePages.some(p => !p.canLeave())) return false;
  exitingSide?.remove();
  while (sidePages.length) sidePages.at(-1).remove(false);
  return true;
}
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || e.defaultPrevented || document.querySelector('.overlay') || !sidePages.length) return;
  e.preventDefault(); sidePages.at(-1).close();
});
export function sidePage({ title, sub, desc, body, actions = [], foot, effect, beforeClose, isDirty, nested = false }) {
  if (!nested && !leaveSidePages()) return { close() {} };
  const parent = sidePages.at(-1), previous = document.activeElement;
  if (parent) parent.panel.hidden = true;
  let pending = false;
  const canLeave = () => !pending && (!beforeClose || beforeClose());
  const remove = (animate = true) => {
    if (sidePages.at(-1) !== entry) return;
    sidePages.pop();
    if (animate && !reduceSideMotion.matches) {
      exitingSide?.remove(); exitingSide = panel;
      panel.inert = true;
      panel.setAttribute('aria-hidden', 'true');
      panel.classList.remove('is-open');
      const finish = () => { panel.remove(); if (exitingSide === panel) exitingSide = null; };
      Promise.allSettled(panel.getAnimations().map(animation => animation.finished)).then(finish);
    } else panel.remove();
    if (parent) parent.panel.hidden = false;
    syncSideLayout();
    if (previous?.isConnected) previous.focus({preventScroll:true});
  };
  const close = () => { if (canLeave()) remove(); };
  const tools = foot || actions.map(a => h('button', {type:'button', class:'btn ' + (a.kind || ''), onclick:async () => {
    if (!a.onClick) return close();
    if (pending) return;
    pending = panel.inert = true;
    try { if (await a.onClick() !== true) remove(); }
    catch (e) { toast(errText(e), 'bad'); }
    finally { pending = false; if (sidePages.at(-1) === entry) panel.inert = false; }
  }}, a.label));
  const signin = h('button', {class:'btn ghost',type:'button',hidden:!!getToken(), onclick:() => loginDialog({onDone:() => { signin.hidden = true; }})}, '登录管理后台');
  const panel = h('section', {class:'side-page', 'aria-label':title},
    h('header', {class:'side-page-head'}, h('div', {}, h('h2', {text:title}), (sub || desc) ? h('small', {text:sub || desc}) : null),
      signin, closeButton(close, !!parent)),
    h('div', {class:'side-page-body'}, body), tools.length ? h('footer', {class:'side-page-foot'}, effect ? hint(effect, {flexBasis:'100%', margin:0}) : null, tools) : null);
  const entry = {panel, close, remove, canLeave, isDirty:() => pending || !!isDirty?.(), offerLogin:() => { signin.hidden = false; }};
  sidePages.push(entry); document.body.append(panel);
  // Establish the offscreen position before starting both layout and panel transitions.
  getComputedStyle(panel).transform;
  panel.classList.add('is-open'); syncSideLayout();
  panel.querySelector('.panel-dismiss').focus({preventScroll:true});
  return entry;
}

// ---------- 通用片段 ----------
let heroStats = null;
export function setHeroStats(s) { heroStats = s || null; }

// 业务口径数字：页面拿到数据后覆盖 hero 右上那四个数（演示页是 商店数/本店商品/覆盖总数/目录物品）。
export function setHeroNumbers(list) {
  const box = document.querySelector('.hero-side');
  if (!box || !Array.isArray(list) || !list.length) return;
  box.replaceChildren(...list.map(([v, u], i) => h('div', { class: i === 0 ? 'k1' : '' }, h('b', { text: String(v) }), h('i', { text: u }))));
}

// 面包屑末级：页面切二级页签时把「/ 货架价格」补到 .top .crumb 上。
export function setCrumbTail(text) {
  const c = $('#crumb');
  if (!c) return;
  c.querySelectorAll('i.tail,b').forEach((n) => n.remove());
  if (text) c.append(h('i', { class: 'tail', text: '/' }), h('b', { text }));
}

// 每条路由在演示页里的横幅取景位置（.hero 的内联 --hpos）。
const HPOS = {
  dashboard: '52% 62%', players: '46% 40%', shop: '62% 58%', stores: '62% 58%',
  rules: '52% 62%', fish: '52% 62%', waters: '50% 58%', hooks: '60% 50%',
  bait: '44% 56%', mail: '58% 64%', tuning: '58% 46%', params: '58% 46%',
  changelog: '62% 88%', release: '62% 88%', about: '50% 58%', audit: '54% 44%',
};

// 页首 = 照片横幅 + 标题/说明 + 四个数字 + 一行口径。
// 结构与演示页 v177 逐层一致：
// .hero > .hero-in > (.hero-main > .eyebrow + h1#title + p.lede) + .hero-side + .factbar > .facts
// 另加 .hero-fade（底部羽化，皮肤靠它把照片压进纸面）。
export function pageHead(title, desc, a3, a4, a5) {
  let opts = {};
  // 主操作行允许同时挂多个控件（例如「控制中心 →」+ 主题切换），
  // 这时第 4 个参数才是 facts，而不是被当成 facts 丢掉。
  if (a3 && a3.nodeType && a4 && a4.nodeType) opts = { actions: [a3, a4], facts: a5 };
  else if (a3 && a3.nodeType) opts = { actions: a3, facts: a4, nums: a5 };
  else if (Array.isArray(a3)) opts = { facts: a3 };
  else if (a3 && typeof a3 === 'object') opts = a3;
  const port = location.port && location.port !== '80' ? location.port : '9500';
  const s = heroStats || {};
  const cells = Array.isArray(opts.nums) && opts.nums.length
    ? opts.nums.map(([v, u]) => [String(v), u])
    : [
      [fmt(s.sessions), '在线玩家'],
      [fmt(s.players), '档案'],
      [fmt(s.tunables), '可调参数'],
      [String(port), '后台端口'],
    ];
  const strip = Array.isArray(opts.facts) ? opts.facts : [];
  const route = currentRoute() || 'dashboard';
  return h('div', { class: 'hero', style: { '--hpos': opts.hpos || HPOS[route] || '52% 62%' } },
    h('div', { class: 'hero-in' },
      h('div', { class: 'hero-main' },
        h('span', { class: 'eyebrow', id: 'eyebrow', text: opts.eyebrow || '' }),
        h('h1', { id: 'title', text: title }),
        desc ? h('p', { class: 'lede', id: 'lede', text: desc }) : null,
        opts.actions ? h('div', { class: 'hero-acts' }, ...[].concat(opts.actions)) : null),
      h('div', { class: 'hero-side', 'aria-label': '服务器要点' },
        ...cells.map(([v, u], i) => h('div', { class: i === 0 ? 'k1' : '' }, h('b', { text: v }), h('i', { text: u })))),
      strip.length ? h('div', { class: 'factbar' },
        h('dl', { class: 'facts' },
          ...strip.map(([k, v]) => h('div', {}, h('dt', { text: k }), h('dd', { text: v }))))) : null),
    h('div', { class: 'hero-fade' }));
}

// 二级页签：演示页是 #tabs > nav.tabs > a[aria-current=page]。
export function pageTabs(items, active, onSelect) {
  if (!Array.isArray(items) || !items.length) return null;
  const route = currentRoute() || 'dashboard';
  const nav = h('nav', { class: 'tabs', 'aria-label': '二级分类' },
    ...items.map(([key, label]) => h('a', {
      href: '#' + route + '/' + key,
      'aria-current': key === active ? 'page' : false,
      onclick: (e) => {
        e.preventDefault();
        if (onSelect) onSelect(key);
        nav.querySelectorAll('a').forEach((a) => {
          if (a === e.currentTarget) a.setAttribute('aria-current', 'page');
          else a.removeAttribute('aria-current');
        });
      },
    }, label)));
  return h('div', { id: 'tabs' }, nav);
}

// 页面主体：.work > section（+ aside）。没有右栏时加 .solo。
export function work(body, aside) {
  const box = h('div', { class: 'work' + (aside ? '' : ' solo'), id: 'work' }, h('section', {}, ...(Array.isArray(body) ? body : [body])));
  if (aside) box.append(h('aside', {}, aside));
  return box;
}

// 右栏信息块：.ib > h2.serif + p.sub + 内容。
export function ib(title, sub, ...body) {
  return h('div', { class: 'ib' },
    title ? h('h2', { class: 'serif', text: title }) : null,
    sub ? h('p', { class: 'sub', text: sub }) : null,
    ...body);
}

// 参数分组块：.group.pblock > .pblock-head(编号/标题/状态) + .two.gapped 行
export function pblock(index, title, desc, body, opts = {}) {
  const no = String(index).padStart(2, '0');
  return h('section', { class: 'group pblock', id: opts.id || 'pg-' + no },
    h('div', { class: 'pblock-head' },
      h('b', { class: 'pno', text: no }),
      h('span', { class: 'ptitle' }, h('b', { text: title }), desc ? h('small', { text: desc }) : null),
      h('span', { class: 'pill', text: opts.pill || '未改动' })),
    h('div', { class: 'two gapped' }, body));
}

export const h2s = (t) => h('h2', { class: 'serif', text: t });
export const h3s = (t) => h('h3', { text: t });
export const hint = (t, style) => h('p', { class: 'hint', text: t, style });
export function note(head, body, style) {
  return h('div', { class: 'note', style }, h('b', { text: head + ' ' }), h('span', { text: body }));
}
export function kv(pairs) {
  return h('dl', {}, ...pairs.filter(Boolean).map(([k, v]) => h('div', {}, h('dt', { text: k }), h('dd', {}, v))));
}
export function bullets(items, ordered = false) {
  return h(ordered ? 'ol' : 'ul', { class: 'bullets' }, ...items.map((t) => h('li', {}, t)));
}
export function pill(text, kind = '') { return h('span', { class: 'pill ' + kind, text }); }
export function brief(cells) {
  return h('div', { class: 'brief' }, ...cells.map(([v, k]) => h('div', {}, h('b', { text: String(v) }), h('small', { text: k }))));
}

// 表格：head 每项可以是 '文字' 或 ['文字','num']；rows 是单元格数组（字符串或节点）。
export function tbl(head, rows, opts = {}) {
  const cls = (h0, i) => (Array.isArray(h0[i]) ? h0[i][1] : '');
  return h('div', { class: 'tbl' + (opts.cls ? ' ' + opts.cls : '') },
    h('table', {},
      h('thead', {}, h('tr', {}, ...head.map((c, i) => h('th', { class: cls(head, i), text: Array.isArray(c) ? c[0] : c })))),
      h('tbody', {}, ...rows.map((r) => h('tr', {}, ...r.map((c, i) => h('td', { class: cls(head, i) }, c)))))));
}

// 运行日志块：.logs > div > (span 时间)(b 来源)(span 内容)。
export function logsBlock(lines) {
  return h('div', { class: 'logs' }, ...lines.map((l) => h('div', {},
    h('span', { text: (l.time || '') + '  ' }),
    h('b', { text: (l.who || '') }),
    h('span', { class: l.kind || '', text: '  ' + (l.text || '') }))));
}

// 「从这里开始」任务行。
export function startGrid(items) {
  return h('div', { class: 'startgrid' }, ...items.map((it, i) => {
    const tag = it.href ? 'a' : 'button';
    return h(tag, {
      class: 'start' + (i === 0 || it.lead ? ' lead' : ''),
      href: it.href || undefined,
      type: it.href ? undefined : 'button',
      onclick: it.onClick,
    },
    h('span', { class: 'si' }, it.icon ? icon(it.icon) : null),
    h('span', { class: 'st' }, h('b', { text: it.title }), h('small', { text: it.sub })),
    h('span', { class: 'go', text: '›' }));
  }));
}
export function section({ title, desc, actions, body, foot, id, cls }) {
  return h('section', { class: 'section ' + (cls || ''), id },
    title ? h('div', { class: 'section-head' }, h('div', {}, h('h2', { text: title }), desc ? h('p', { text: desc }) : null),
      actions ? h('div', { class: 'actions' }, actions) : null) : null,
    h('div', { class: 'section-body' }, body),
    foot ? h('div', { class: 'section-foot' }, foot) : null);
}
export function callout(kind, content, iconName) {
  return h('div', { class: 'callout ' + kind }, icon(iconName || (kind === 'warn' || kind === 'bad' ? 'alert' : 'info')), h('div', { class: 'grow' }, content));
}
export function badge(text, kind = '', dot = false) { return h('span', { class: 'badge ' + kind + (dot ? ' dot' : ''), text }); }
export function empty(title, desc, action) {
  return h('div', { class: 'empty' }, h('b', { text: title }), desc ? h('div', { text: desc }) : null, action || null);
}
export function loading(lines = 3) {
  return h('div', { class: 'stack', style: { padding: '8px 0' } }, Array.from({ length: lines }, (_, i) => h('div', { class: 'skeleton', style: { width: (90 - i * 15) + '%' } })));
}
export function btn(label, onClick, kind = '', extra = {}) {
  return h('button', { class: 'btn ' + kind, onclick: onClick, type: 'button', ...extra }, extra.icon ? icon(extra.icon) : null, label);
}
export function toggleEl({ checked, onChange, disabled, label, id }) {
  const input = h('input', { type: 'checkbox', id, disabled, onchange: (e) => onChange && onChange(e.target.checked) });
  input.checked = !!checked;
  const sw = h('label', { class: 'sw' }, input);
  return label ? h('span', { class: 'swrow' }, sw, h('span', { class: 'small muted', text: label })) : sw;
}
export function segmented(options, value, onChange) {
  const box = h('div', { class: 'seg', role: 'radiogroup' });
  const render = (v) => {
    box.replaceChildren(...options.map(([val, label]) => h('button', {
      type: 'button', class: String(val) === String(v) ? 'on' : '', role: 'radio', 'aria-checked': String(String(val) === String(v)),
      // 分段按钮常被放进 <label class="row"> 里：label 会把点击转发给第一个可标注控件，
      // 导致「点第二项又跳回第一项」。阻止默认行为与冒泡，避免被 label 再点一次。
      onclick: (e) => { e.preventDefault(); e.stopPropagation(); render(val); onChange(val); },
    }, label)));
  };
  render(value);
  return box;
}
export function tabs(items, active, onChange) {
  return pageTabs(items, active, onChange);
}
export function searchBox(placeholder, onInput, value = '') {
  const input = h('input', { type: 'search', placeholder, value, oninput: (e) => onInput(e.target.value) });
  return h('div', { class: 'search' }, input);
}
export function debounce(fn, ms = 250) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

// ---------- 表单模型 ----------
// 统一处理「草稿 → 校验 → 保存」：每个字段登记原值，改动后底部出现保存条。
// spec: {key, label, help, kind:'int'|'float'|'bool'|'string'|'select'|'text', min, max, step, unit, def, options, placeholder, advanced}
export class Form {
  constructor({ onSave, onChange } = {}) {
    this.fields = new Map();
    this.onSave = onSave;
    this.onChange = onChange;
  }
  field(spec, value) {
    const f = { spec, original: normalize(spec, value), input: null, row: null, errEl: null };
    this.fields.set(spec.key, f);
    return f;
  }
  value(key) {
    const f = this.fields.get(key);
    if (!f) return undefined;
    return readInput(f);
  }
  dirtyKeys() {
    return [...this.fields.values()].filter((f) => f.input && !sameValue(f)).map((f) => f.spec.key);
  }
  isDirty() { return this.dirtyKeys().length > 0; }
  validate(keys) {
    let ok = true;
    for (const key of keys || this.dirtyKeys()) {
      const f = this.fields.get(key);
      if (!f) continue;
      const msg = validate(f.spec, readInput(f));
      setError(f, msg);
      if (msg) ok = false;
    }
    return ok;
  }
  values(keys) {
    const out = {};
    for (const key of keys || this.dirtyKeys()) out[key] = readInput(this.fields.get(key));
    return out;
  }
  reset() {
    for (const f of this.fields.values()) { if (f.input) writeInput(f, f.original); setError(f, ''); }
    this.refresh();
  }
  commit(values) {
    for (const [k, v] of Object.entries(values || this.values())) {
      const f = this.fields.get(k);
      if (f) f.original = normalize(f.spec, v);
    }
    this.refresh();
  }
  refresh() {
    for (const f of this.fields.values()) {
      if (f.row) f.row.classList.toggle('changed', !!f.input && String(readInput(f)) !== String(f.original));
    }
    this.onChange && this.onChange(this);
  }
  // 设置行：左说明右控件
  row(spec, value, opts = {}) {
    const f = this.field(spec, value);
    const control = buildControl(this, f);
    const metaBits = [];
    if (spec.kind === 'int' || spec.kind === 'float') {
      if (spec.max !== undefined) metaBits.push('范围 ' + (spec.min ?? 0) + ' – ' + spec.max + (spec.unit ? ' ' + spec.unit : ''));
    }
    if (spec.def !== undefined && spec.def !== '') metaBits.push('默认 ' + (spec.kind === 'bool' ? (String(spec.def) === '1' || spec.def === true ? '开' : '关') : spec.def + (spec.unit && spec.kind !== 'bool' ? ' ' + spec.unit : '')));
    f.errEl = h('div', { class: 's-error', hidden: true });
    const subBits = [spec.help || '', ...metaBits].filter(Boolean).join(' · ');
    f.row = h('label', { class: 'row' + (opts.wide ? ' wide' : '') },
      h('span', { class: 'lab' }, h('b', { text: spec.label }), subBits ? h('small', { text: subBits }) : null),
      h('span', { class: 'ctrl' }, control),
      f.errEl);
    return f.row;
  }
  // 字段：标签在上
  stacked(spec, value) {
    const f = this.field(spec, value);
    const control = buildControl(this, f);
    f.errEl = h('div', { class: 'help', style: { color: '#f08a97' }, hidden: true });
    f.row = h('div', { class: 'field' + (spec.span ? ' span-2' : '') },
      h('label', { for: f.input.id, text: spec.label }), control,
      spec.help ? h('div', { class: 'help', text: spec.help }) : null, f.errEl);
    return f.row;
  }
}
let fieldSeq = 0;
function buildControl(form, f) {
  const s = f.spec;
  const id = 'f_' + (s.id || s.key).replace(/[^\w-]/g, '_') + '_' + (++fieldSeq);
  const onInput = () => { setError(f, ''); form.refresh(); };
  if (s.kind === 'bool') {
    const input = h('input', { type: 'checkbox', id, onchange: onInput });
    input.checked = f.original === '1';
    f.input = input;
    return h('label', { class: 'sw' }, input);
  }
  if (s.kind === 'select') {
    const input = h('select', { class: 'select', id, onchange: onInput }, (s.options || []).map(([v, l]) => h('option', { value: v, text: l })));
    input.value = f.original;
    f.input = input;
    return input;
  }
  if (s.kind === 'text') {
    const input = h('textarea', { class: 'textarea', id, rows: s.rows || 4, placeholder: s.placeholder || '', oninput: onInput });
    input.value = f.original;
    f.input = input;
    return input;
  }
  const numeric = s.kind === 'int' || s.kind === 'float';
  const input = h('input', {
    class: 'input' + (numeric ? ' num' : ''), id, type: s.secret ? 'password' : 'text', inputmode: numeric ? 'decimal' : null,
    placeholder: s.placeholder || (s.def !== undefined && s.def !== '' ? String(s.def) : ''), autocomplete: s.secret ? 'new-password' : 'off', oninput: onInput,
  });
  input.value = f.original;
  f.input = input;
  if (s.unit) return unitWrap(input, s.unit);
  return input;
}
// 单位放在输入框右侧内部，按单位文字宽度留出空间，避免和数字重叠
export function unitWrap(input, unit) {
  const wrap = h('div', { class: 'input-wrap has-unit' }, input, h('span', { class: 'unit', text: unit }));
  const em = [...unit].reduce((w, ch) => w + (/[\x00-\x7f]/.test(ch) ? 0.58 : 1), 0);
  wrap.style.setProperty('--unit-w', em.toFixed(2) + 'em');
  return wrap;
}
function normalize(spec, v) {
  if (spec.kind === 'bool') return v === true || v === 1 || v === '1' || v === 'true' ? '1' : '0';
  return v === undefined || v === null ? '' : String(v);
}
// 数值字段用数值比较：数据库里的 59 与 59.0、59.00 是同一个值，不能算「改过」。
function sameValue(f) {
  const now = readInput(f);
  const was = String(f.original);
  const kind = f.spec.kind;
  if (kind === 'int' || kind === 'float') {
    const a = Number.parseFloat(now);
    const b = Number.parseFloat(was);
    if (Number.isFinite(a) && Number.isFinite(b)) return Math.abs(a - b) < 1e-9;
    return now === '' && was === '';
  }
  return now === was;
}
function readInput(f) {
  if (!f.input) return f.original;
  if (f.spec.kind === 'bool') return f.input.checked ? '1' : '0';
  return String(f.input.value).trim();
}
function writeInput(f, v) {
  if (f.spec.kind === 'bool') f.input.checked = v === '1';
  else f.input.value = v;
}
function validate(spec, raw) {
  if (spec.kind !== 'int' && spec.kind !== 'float') {
    if (spec.required && !raw) return '请填写' + spec.label;
    if (spec.pattern && raw && !spec.pattern.test(raw)) return spec.patternMsg || '格式不正确';
    return '';
  }
  if (raw === '') return spec.optional ? '' : '请填写数值';
  const n = Number(raw);
  if (!Number.isFinite(n)) return '请填写数字';
  if (spec.kind === 'int' && !Number.isInteger(n)) return '请填写整数';
  const lo = spec.min ?? (spec.max !== undefined ? 0 : undefined);
  if (lo !== undefined && n < lo) return '不能小于 ' + lo;
  if (spec.max !== undefined && n > spec.max) return '不能大于 ' + spec.max;
  return '';
}
function setError(f, msg) {
  if (!f || !f.input) return;
  f.input.setAttribute('aria-invalid', msg ? 'true' : 'false');
  if (f.errEl) { f.errEl.hidden = !msg; f.errEl.textContent = msg; }
}

// 保存条：默认是右下角浮层（一页一个）；传 inline 时渲染到指定容器里，
// 用于「改完就在内容底部核对并保存」的页面（演示页是这种内联按钮）。
let savebarEl = null;
// 浮层保存条全局只有一个：记下当前持有者，旧页面迟到的保存结果不能再把它点亮或借它提交。
let savebarOwner = null;
export function savebar(form, { onSave, label, inline, effect } = {}) {
  const owner = {};
  if (!inline) savebarOwner = owner;
  const live = () => !!inline || savebarOwner === owner;
  let bar = inline || null;
  if (!bar) {
    if (!savebarEl) { savebarEl = h('div', { class: 'savebar', role: 'status' }); document.body.append(savebarEl); }
    bar = savebarEl;
  }
  const count = h('span');
  let saving = false;
  const saveBtn = btn('保存修改', async () => {
    const keys = form.dirtyKeys();
    if (saving || !keys.length || !live()) return;
    if (!form.validate(keys)) { toast('有填写不正确的项，请检查标红的输入框', 'bad'); return; }
    const values = form.values(keys);
    saving = saveBtn.disabled = true;
    try { await onSave(values, keys); form.commit(values); toast(effect ? '已保存。' + effect : '已保存'); }
    catch (e) { toast(errText(e), 'bad'); }
    finally { saving = false; update(); }
  }, 'primary sm');
  bar.replaceChildren(count, btn('放弃', () => form.reset(), 'ghost sm'), saveBtn);
  const update = () => {
    if (!live()) return;
    const n = form.dirtyKeys().length;
    if (inline && n === 0) count.replaceChildren(h('span', { class: 'hint', text: '没有改动' }));
    else count.replaceChildren((label || ''), h('b', { text: n }), ' 项修改尚未保存');
    if (effect) count.append(h('small', {style:{display:'block'}, text:effect}));
    saveBtn.disabled = saving || n === 0;
    bar.classList.toggle('on', n > 0);
  };
  form.onChange = update;
  update();
  return update;
}
export function hideSavebar() { savebarOwner = null; if (savebarEl) savebarEl.classList.remove('on'); }

// 页面生命周期：切换路由或重新渲染前释放定时器、监听器。
let pageCleanup = null;
function cleanupPage() {
  const fn = pageCleanup;
  pageCleanup = null;
  if (!fn) return;
  try { fn(); } catch (e) {}
}

// ---------- 路由 ----------
const routes = new Map();
let current = null;
let guardFn = null;
export function route(name, def) { routes.set(name, def); }
export function routeDefs() { return routes; }
export function currentRoute() { return current; }
export function parseHash() {
  const raw = location.hash.replace(/^#\/?/, '');
  const [name, ...rest] = raw.split('/');
  return { name: name || 'dashboard', params: rest.map(decodeURIComponent) };
}
export function navigate(name, ...params) {
  const hash = '#' + [name, ...params.map(encodeURIComponent)].join('/');
  if (location.hash === hash) render(); else location.hash = hash;
}
export function replaceHash(hash) {
  history.replaceState(null, '', hash);
  lastHash = location.hash;
}
// 页内切换保留浏览器历史，但不触发整页路由重绘。
export function pushHash(hash) {
  if (location.hash !== hash) history.pushState(null, '', hash);
  lastHash = location.hash;
}
let renderID = 0;
export async function render() {
  const { name, params } = parseHash();
  const def = routes.get(name) || routes.get('dashboard');
  const key = routes.has(name) ? name : 'dashboard';
  if (!$('#view')) return; // 还在登录页或框架未建好，boot 完成后会再渲染
  if (!leaveSidePages()) return;
  const id = ++renderID;
  cleanupPage();
  hideSavebar();
  guardFn = null;
  current = key;
  document.dispatchEvent(new CustomEvent('rf4:route', { detail: { name: key } }));
  const root = $('#view');
  root.inert = true;
  // 不先把页面清空。上一次这里是 replaceChildren(loading)：旧页立刻消失、新页还要等模块加载，
  // 于是 hero 照片整块闪一下。现在旧内容原地留着并轻微压暗，新内容算好之后一次换掉。
  // 先不压暗：模块已经预取过时切换只要一两帧，压暗反而像闪。超过 130ms 才提示「在换」。
  const busyTimer = setTimeout(() => { if (renderID === id) root.classList.add('is-busy'); }, 130);
  try {
    const scope = {
      isCurrent: () => renderID === id,
      setLeaveGuard: fn => { if (renderID === id) guardFn = fn; },
      setPageCleanup: fn => { if (renderID === id) pageCleanup = fn; else fn?.(); },
    };
    const node = await def.render(params, scope);
    clearTimeout(busyTimer);
    if (renderID !== id) return;
    const kids = Array.isArray(node) ? node.filter(Boolean) : [node];
    // 演示页即使没有二级页签也留一个 #tabs 占位（hero 与 .work 之间的 18px 留白）。
    if (!kids.some((n) => n && n.id === 'tabs')) kids.splice(1, 0, h('div', { id: 'tabs' }));
    const swap = () => { if (renderID !== id) return; root.replaceChildren(...kids); translateDom(root); root.inert = false; window.scrollTo(0, 0); };
    const reduce = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (typeof document.startViewTransition === 'function' && !reduce) {
      // 支持 View Transitions 的浏览器用一次 180ms 交叉淡入，避免硬切。
      const done = () => { if (renderID === id) root.classList.remove('is-busy'); };
      document.startViewTransition(swap).finished.then(done, done);
    } else {
      swap();
      root.classList.remove('is-busy');
    }
  } catch (e) {
    clearTimeout(busyTimer);
    if (renderID !== id) return;
    root.inert = false;
    root.classList.remove('is-busy');
    if (e && e.status === 401) return;
    root.replaceChildren(h('div', { class: 'work solo' }, h('section', {}, callout('bad', ['页面加载失败：', errText(e)]))));
  }
}
let unloadConfirmed = false;
const sideDirty = () => sidePages.some(p => p.isDirty());
window.addEventListener('beforeunload', (e) => {
  if (unloadConfirmed) return;
  if ((guardFn && guardFn()) || sideDirty()) { e.preventDefault(); e.returnValue = ''; }
});
// 「刷新本页」：主页面和侧页的未保存修改都要先确认，确认过后不再弹浏览器自带的离开提示。
export function reloadPage() {
  if (!sidePages.every(p => p.canLeave())) return;
  if (guardFn && guardFn() && !confirm('有修改还没保存，确定刷新吗？')) return;
  unloadConfirmed = true;
  location.reload();
}
let lastHash = location.hash;
window.addEventListener('hashchange', () => {
  if (guardFn && guardFn() && !confirm('有修改还没保存，确定离开吗？')) {
    history.replaceState(null, '', lastHash);
    return;
  }
  if (!leaveSidePages()) { history.replaceState(null, '', lastHash); return; }
  lastHash = location.hash;
  render();
});

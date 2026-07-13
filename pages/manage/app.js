const PLUGIN = 'astrbot_plugin_juben_npc';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const CHECKIN_TEXTS = {
  title: { label: '标题', text: '{title}', x: 0.07, y: 0.14, size: 0.062, color: '#ffffff', bold: true },
  reward: { label: '奖励', text: '{reward}', x: 0.08, y: 0.30, size: 0.042, color: '#eaf4ff', bold: true },
  coins: { label: '星币', text: '当前星币：{coins}', x: 0.08, y: 0.41, size: 0.038, color: '#d7e6f5', bold: false },
  message: { label: '附言', text: '{message}', x: 0.08, y: 0.58, size: 0.03, color: '#c8d9ea', bold: false },
  user: { label: '打开者', text: '打开者：{user_name}', x: 0.08, y: 0.70, size: 0.027, color: '#b8cadd', bold: false },
};
const STATUS_TEXTS = {
  user: { label: '打开者', text: '打开者：{user_name}｜ID：{user_id}', x: 0.45, y: 0.105, size: 0.02, color: '#6d9bc6', bold: false },
  name: { label: '角色名', text: '{character_name}', x: 0.441, y: 0.19, size: 0.042, color: '#172033', bold: true },
  subtitle: { label: '副标题', text: '{subtitle_name}  |  {quality}  |  {bonus}', x: 0.441, y: 0.265, size: 0.02, color: '#6d9bc6', bold: true },
  stars: { label: '星级', text: '{stars}', x: 0.441, y: 0.323, size: 0.031, color: '#f5b642', bold: true },
  level: { label: '等级经验', text: 'Lv.{level}  {current}/{need} EXP', x: 0.441, y: 0.39, size: 0.021, color: '#6d9bc6', bold: true },
};

const FONT_OPTIONS = [
  ['default', '默认中文字体（Noto）'], ['msyh', '微软雅黑'], ['simhei', '黑体'], ['simsun', '宋体'], ['kaiti', '楷体'],
  ['fangsong', '仿宋'], ['dengxian', '等线'], ['lisu', '隶书'], ['youyuan', '幼圆'], ['stxingkai', '华文行楷'],
  ['stfangsong', '华文仿宋'], ['stsong', '华文宋体'], ['stxihei', '华文细黑'],
  ['zcool_kuaile', '站酷快乐体（可爱）'], ['mashanzheng', '马善政毛笔（手写）'], ['zcool_qingke', '站酷庆科黄油体（圆润）'],
  ['longcang', '龙藏体（飘逸）'], ['liujianmaocao', '刘建毛草（签名字）'],
];
const FONT_OPTIONS_HTML = FONT_OPTIONS.map(([value, label]) => `<option value="${value}">${label}</option>`).join('');
const TEXT_STYLE_DEFAULTS = {
  font_family: '', font_weight: 400, shadow_color: '#1c2a40', shadow_offset_x: 0, shadow_offset_y: 2, shadow_blur: 2.5, shadow_opacity: 64,
};

let characters = [];
let players = [];
let settings = {};
let checkinTemplates = [];
let statusTemplates = [];
let selectedId = '';
let selectedCheckinId = '';
let selectedStatusId = '';
let selectedFilter = 'all';
let activeImagePasteHandler = null;
let checkinPreviewTimer = 0;
let statusPreviewTimer = 0;

const bridge = () => window.AstrBotPluginPage || {};
const endpoint = (path) => String(path || '').trim().replace(/^\/+/, '');
const normalizeResponse = (result) => result?.data || result || {};

async function parseResponse(response) {
  const payload = await response.json();
  if (!response.ok || payload?.status === 'error') throw new Error(payload?.message || `请求失败（HTTP ${response.status}）`);
  return payload;
}
async function apiGet(path) {
  const api = bridge(); const target = endpoint(path);
  if (api.apiGet) return api.apiGet(target);
  if (api.request) return api.request({ method: 'GET', path: target });
  return parseResponse(await fetch(`/api/plug/${encodeURIComponent(PLUGIN)}/${target}`));
}
async function apiPost(path, data) {
  const api = bridge(); const target = endpoint(path);
  if (api.apiPost) return api.apiPost(target, data);
  if (api.request) return api.request({ method: 'POST', path: target, data });
  return parseResponse(await fetch(`/api/plug/${encodeURIComponent(PLUGIN)}/${target}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  }));
}
async function apiDelete(path) { return apiPost(`${path}/delete`, {}); }

function fileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('读取图片失败，请重新选择文件。'));
    reader.onload = () => resolve(String(reader.result || ''));
    reader.readAsDataURL(file);
  });
}
async function upload(path, file) {
  const api = bridge(); const target = endpoint(path);
  let bridgeError = null;
  if (api.upload) {
    try { return await api.upload(target, file); } catch (error) { bridgeError = error; }
  }
  if (api.apiPost && file && file.size <= 10 * 1024 * 1024) {
    try {
      return await api.apiPost(`${target}/data-url`, { filename: file.name || 'upload.png', data_url: await fileAsDataUrl(file) });
    } catch (error) {
      throw new Error(error?.message || bridgeError?.message || '图片上传失败');
    }
  }
  if (bridgeError) throw bridgeError;
  const form = new FormData(); form.append('file', file);
  return parseResponse(await fetch(`/api/plug/${encodeURIComponent(PLUGIN)}/${target}`, { method: 'POST', body: form }));
}

function assetUrl(image, kind = 'assets') {
  return image ? `/api/plug/${PLUGIN}/${kind}/${encodeURIComponent(image)}` : '';
}
function escapeHtml(value) {
  return String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;');
}
function kindLabel(kind) {
  return ({ companion: '同伴', skin: '皮肤', item: '道具', experience_ball: '经验球' })[kind] || '条目';
}
function exclusiveItemNames(entry) {
  const raw = entry?.exclusive_items?.length ? entry.exclusive_items : (entry?.exclusive_item || '');
  const values = Array.isArray(raw) ? raw : String(raw).split(/[\r\n,，;；]+/);
  return [...new Set(values.map((value) => String(value?.name || value || '').trim()).filter(Boolean))];
}
function toast(message) {
  const el = $('#toast'); el.textContent = message; el.classList.add('show');
  window.setTimeout(() => el.classList.remove('show'), 2400);
}
function errorText(error) { return error?.message || '操作失败，请查看浏览器控制台。'; }
async function safely(action) { try { await action(); } catch (error) { console.error(error); toast(errorText(error)); } }
function confirmDelete(button, label) {
  const now = Date.now(); const until = Number(button.dataset.confirmUntil || 0);
  if (until > now) {
    window.clearTimeout(Number(button.dataset.confirmTimer || 0));
    button.textContent = button.dataset.defaultLabel || '删除';
    delete button.dataset.confirmUntil; delete button.dataset.confirmTimer;
    return true;
  }
  button.dataset.defaultLabel = button.textContent;
  button.dataset.confirmUntil = String(now + 5000);
  button.textContent = '再次点击确认';
  toast(`请在 5 秒内再次点击，确认${label}。`);
  button.dataset.confirmTimer = String(window.setTimeout(() => {
    button.textContent = button.dataset.defaultLabel || '删除';
    delete button.dataset.confirmUntil; delete button.dataset.confirmTimer;
  }, 5000));
  return false;
}

function setValue(form, name, value = '') { if (form?.elements?.[name]) form.elements[name].value = value ?? ''; }
function setChecked(form, name, value = false) { if (form?.elements?.[name]) form.elements[name].checked = Boolean(value); }
function numberValue(value, fallback = 0) { const parsed = Number(value); return Number.isFinite(parsed) ? parsed : fallback; }

async function loadAll() {
  const payload = normalizeResponse(await apiGet('/characters'));
  characters = payload.characters || [];
  players = payload.players || [];
  settings = payload.settings || settings;
  checkinTemplates = payload.checkin_templates || [];
  statusTemplates = payload.status_templates || [];
  if (!selectedId && characters[0]) selectedId = characters[0].id;
  if (!selectedCheckinId && checkinTemplates[0]) selectedCheckinId = checkinTemplates[0].id;
  if (!selectedStatusId && statusTemplates[0]) selectedStatusId = statusTemplates[0].id;
  renderColorGroup(); renderList(); renderParentOptions(); renderBoundOptions(); renderPlayerOptions(); renderAssetOptions(); fillSettings();
  fillCharacter(characters.find((entry) => entry.id === selectedId) || characters[0]);
  renderTemplateList('checkin'); fillTemplate('checkin', checkinTemplates.find((entry) => entry.id === selectedCheckinId) || checkinTemplates[0]);
  renderTemplateList('status'); fillTemplate('status', statusTemplates.find((entry) => entry.id === selectedStatusId) || statusTemplates[0]);
}

function renderColorGroup() {
  const active = $('.color-tabs button.active')?.dataset.colorGroup || 'companion';
  $$('[data-color-group]').forEach((element) => {
    if (!element.matches('.color-tabs button')) element.hidden = element.dataset.colorGroup !== active;
  });
}
function fillSettings() {
  const form = $('#settings-form');
  Object.entries(settings).forEach(([key, value]) => { if (form.elements[key]) form.elements[key].value = value; });
}
function readSettings() {
  return Object.fromEntries($$('#settings-form input[type="color"]').map((input) => [input.name, input.value]));
}

function renderList() {
  const list = $('#character-list'); list.innerHTML = '';
  const addHeading = (text) => { const heading = document.createElement('div'); heading.className = 'list-heading'; heading.textContent = text; list.appendChild(heading); };
  const addEntry = (entry) => {
    const item = document.createElement('button'); item.type = 'button';
    item.className = `character-item ${entry.id === selectedId ? 'active' : ''} ${entry.kind === 'skin' ? 'skin-entry' : ''}`;
    const description = entry.kind === 'experience_ball'
      ? `${entry.exp_amount || 0} EXP · 权重 ${entry.draw_weight || 1} ${entry.in_pool ? '· 奖池' : ''}`
      : entry.kind === 'item'
        ? `道具 · 权重 ${entry.draw_weight || 1} ${entry.in_pool ? '· 奖池' : ''}`
      : `${entry.english_name || entry.quality || entry.star || '—'} ${entry.in_pool ? '· 奖池' : ''}`;
    item.innerHTML = `<img src="${entry.preview || assetUrl(entry.image)}" alt="" /><span><strong>${escapeHtml(entry.kind === 'skin' ? `↳ ${entry.name}` : entry.name)}</strong><span>${escapeHtml(description)}</span></span>`;
    item.addEventListener('click', () => { selectedId = entry.id; renderList(); fillCharacter(entry); });
    list.appendChild(item);
  };
  const filtered = selectedFilter === 'all' ? characters : characters.filter((entry) => entry.kind === selectedFilter);
  ['companion', 'skin', 'item', 'experience_ball'].forEach((kind) => {
    const entries = filtered.filter((entry) => entry.kind === kind).sort((a, b) => String(a.name).localeCompare(String(b.name), 'zh-CN'));
    if (!entries.length) return;
    addHeading(kindLabel(kind)); entries.forEach(addEntry);
  });
  if (!list.childElementCount) list.innerHTML = '<p class="empty">该分类暂无条目。</p>';
}

function renderParentOptions() {
  const select = $('#parent-companion'); const previous = select.value;
  select.innerHTML = '<option value="">请选择所属同伴</option>';
  characters.filter((entry) => entry.kind === 'companion').forEach((entry) => {
    const option = document.createElement('option'); option.value = entry.id; option.textContent = `${entry.name} / ${entry.english_name || '—'}`; select.appendChild(option);
  });
  if ([...select.options].some((option) => option.value === previous)) select.value = previous;
}
function renderBoundOptions() {
  $$('.template-bound-entry').forEach((select) => {
    const previous = select.value;
    select.innerHTML = '<option value="">通用模板（所有未绑定角色）</option>';
    ['companion', 'skin'].forEach((kind) => characters.filter((entry) => entry.kind === kind).forEach((entry) => {
      const option = document.createElement('option'); option.value = entry.id; option.textContent = `${kindLabel(kind)} · ${entry.name}`; select.appendChild(option);
    }));
    if ([...select.options].some((option) => option.value === previous)) select.value = previous;
  });
}
function renderPlayerOptions() {
  const select = $('#known-player'); select.innerHTML = '<option value="">手动填写</option>';
  players.forEach((player, index) => { const option = document.createElement('option'); option.value = String(index); option.textContent = `${player.name} / ${player.user_id} / ${player.scope_id}`; select.appendChild(option); });
}
function renderAssetOptions() {
  const assetSelect = $('#asset-character'); assetSelect.innerHTML = '';
  characters.filter((entry) => ['companion', 'skin', 'item'].includes(entry.kind)).forEach((entry) => {
    const option = document.createElement('option'); option.value = entry.id; option.textContent = `${kindLabel(entry.kind)} · ${entry.name} / ${entry.english_name || entry.quality || '—'}`; assetSelect.appendChild(option);
  });
  const exclusive = $('#grant-exclusive'); exclusive.innerHTML = '<option value="">选择要发放的专属物品</option>';
  characters.filter((entry) => entry.kind === 'companion').forEach((entry) => exclusiveItemNames(entry).forEach((name) => {
    const option = document.createElement('option'); option.value = entry.id; option.dataset.exclusiveName = name; option.textContent = `${entry.name} · ${name}`; exclusive.appendChild(option);
  }));
}

function toggleKindFields(kind) {
  $$('.companion-only').forEach((element) => element.classList.toggle('hidden', kind !== 'companion'));
  $$('.skin-only').forEach((element) => element.classList.toggle('hidden', kind !== 'skin'));
  $$('.item-only').forEach((element) => element.classList.toggle('hidden', kind !== 'item'));
  $$('.experience-only').forEach((element) => element.classList.toggle('hidden', kind !== 'experience_ball'));
  $$('.weighted-only').forEach((element) => element.classList.toggle('hidden', !['item', 'experience_ball'].includes(kind)));
  $$('.quality-field').forEach((element) => element.classList.toggle('hidden', kind === 'item'));
  const form = $('#character-form');
  form.elements.quality.placeholder = kind === 'experience_ball' ? '经验球' : 'SSR / SR / R';
}
function fillCharacter(entry) {
  const form = $('#character-form');
  if (!entry) { form.reset(); toggleKindFields('companion'); return; }
  selectedId = entry.id;
  setValue(form, 'kind', entry.kind || 'companion'); setValue(form, 'id', entry.id); setValue(form, 'name', entry.name); setValue(form, 'english_name', entry.english_name || entry.skin || '');
  setValue(form, 'quality', entry.quality || entry.star || 'R'); setValue(form, 'parent_id', entry.parent_id || ''); setValue(form, 'exclusive_items', exclusiveItemNames(entry).join('\n'));
  setValue(form, 'route', entry.route || ''); setValue(form, 'bonus', entry.bonus || ''); setValue(form, 'intro', entry.intro || ''); setValue(form, 'effect', entry.effect || ''); setValue(form, 'image', entry.image || '');
  setValue(form, 'focal_x', entry.focal_x ?? 0.5); setValue(form, 'focal_y', entry.focal_y ?? 0.5); setValue(form, 'exp_amount', entry.exp_amount ?? 10); setValue(form, 'draw_weight', entry.draw_weight ?? 10); setChecked(form, 'in_pool', entry.in_pool);
  const skills = entry.skills || []; [0, 1, 2].forEach((index) => { setValue(form, `skill${index}`, skills[index]?.[0] || ''); setValue(form, `skill${index}Desc`, skills[index]?.[1] || ''); });
  $('#parent-companion').value = entry.parent_id || '';
  toggleKindFields(entry.kind || 'companion');
  $('#preview-image').src = entry.preview || assetUrl(entry.image); $('#preview-title').textContent = entry.name || '未命名条目';
  $('#preview-subtitle').textContent = entry.kind === 'experience_ball'
    ? `抽中后直接 +${entry.exp_amount || 0} EXP，权重 ${entry.draw_weight || 1}`
    : entry.kind === 'item'
      ? `道具 · 抽取权重 ${entry.draw_weight || 1}`
      : `${kindLabel(entry.kind)} · ${entry.english_name || entry.quality || '—'}`;
}
function readCharacter() {
  const form = $('#character-form'); const kind = form.elements.kind.value;
  return {
    id: form.elements.id.value.trim(), kind, name: form.elements.name.value.trim(), english_name: form.elements.english_name.value.trim(), quality: form.elements.quality.value.trim(), parent_id: form.elements.parent_id.value,
    exclusive_items: form.elements.exclusive_items.value.trim(), route: form.elements.route.value.trim(), bonus: form.elements.bonus.value.trim(), intro: form.elements.intro.value.trim(), effect: form.elements.effect.value.trim(), image: form.elements.image.value.trim(), in_pool: form.elements.in_pool.checked,
    focal_x: numberValue(form.elements.focal_x.value, 0.5), focal_y: numberValue(form.elements.focal_y.value, 0.5), exp_amount: numberValue(form.elements.exp_amount.value, 10), draw_weight: numberValue(form.elements.draw_weight.value, 10),
    skills: [[form.elements.skill0.value.trim(), form.elements.skill0Desc.value.trim()], [form.elements.skill1.value.trim(), form.elements.skill1Desc.value.trim()], [form.elements.skill2.value.trim(), form.elements.skill2Desc.value.trim()]],
  };
}

function blobAsFile(blob, fallback) {
  if (blob instanceof File) return blob;
  const extension = ({ 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/png': 'png' })[blob.type] || 'png';
  return new File([blob], fallback.replace(/\.[^.]+$/, `.${extension}`), { type: blob.type || 'image/png' });
}
function bindImageDropzone(zoneSelector, inputSelector, handler, fallbackName) {
  const zone = $(zoneSelector); const input = $(inputSelector);
  input.addEventListener('change', () => safely(() => handler(input.files[0])));
  zone.addEventListener('focus', () => { activeImagePasteHandler = handler; });
  zone.addEventListener('click', () => { activeImagePasteHandler = handler; zone.focus(); input.click(); });
  zone.addEventListener('dragover', (event) => { event.preventDefault(); zone.classList.add('dragging'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragging'));
  zone.addEventListener('drop', (event) => { event.preventDefault(); zone.classList.remove('dragging'); safely(() => handler(event.dataTransfer.files[0])); });
  zone.addEventListener('paste', (event) => {
    const item = [...(event.clipboardData?.items || [])].find((candidate) => candidate.type?.startsWith('image/'));
    if (!item) { toast('剪贴板中没有真实图片文件。'); return; }
    event.preventDefault(); safely(() => handler(blobAsFile(item.getAsFile(), fallbackName)));
  });
  document.addEventListener('paste', (event) => {
    if (event.defaultPrevented || activeImagePasteHandler !== handler) return;
    const item = [...(event.clipboardData?.items || [])].find((candidate) => candidate.type?.startsWith('image/'));
    if (!item) return;
    event.preventDefault(); safely(() => handler(blobAsFile(item.getAsFile(), fallbackName)));
  });
  document.addEventListener('focusin', (event) => { if (!zone.contains(event.target)) activeImagePasteHandler = null; });
}
async function uploadEntryFile(file) {
  if (!file?.type?.startsWith('image/')) { toast('请粘贴或选择真实图片文件；图片链接不能直接上传。'); return; }
  const result = normalizeResponse(await upload('/upload-image', file));
  if (!result.image) throw new Error('图片上传失败。');
  $('#character-form').elements.image.value = result.image; $('#preview-image').src = URL.createObjectURL(file); toast('图片已上传，保存条目后生效。');
}

function templateDefaults(type) {
  const texts = type === 'checkin' ? CHECKIN_TEXTS : STATUS_TEXTS;
  return {
    id: '', name: '', bound_entry_id: '', priority: 0, background_image: '', panel_image: '', portrait_frame_image: '', image: '', enabled: true, show_companion: true, text_style_version: 2,
    portrait_scale: 1, portrait_offset_x: 0, portrait_offset_y: 0, font_family: 'default', panel_color: type === 'checkin' ? '#152238' : '#ffffff', message: type === 'checkin' ? '今日也要和同伴一起前进。' : '',
    texts: Object.fromEntries(Object.entries(texts).map(([key, value]) => [key, { ...value }])),
  };
}
function textRow(container, key, config, label = '') {
  const row = document.createElement('div'); row.className = 'text-row'; row.dataset.textKey = key;
  row.innerHTML = `<strong>${escapeHtml(label || config.label || key)}</strong><input data-field="text" aria-label="文字内容" /><input data-field="x" aria-label="X 坐标" type="number" min="0" max="1" step="0.01" /><input data-field="y" aria-label="Y 坐标" type="number" min="0" max="1" step="0.01" /><input data-field="size" aria-label="字号" type="number" min="0.015" max="0.15" step="0.005" /><select data-field="font_family" aria-label="字体"><option value="">继承模板字体</option>${FONT_OPTIONS_HTML}</select><select data-field="font_weight" aria-label="字重"><option value="100">极细 100</option><option value="200">纤细 200</option><option value="300">细体 300</option><option value="400">常规 400</option><option value="500">中等 500</option><option value="600">半粗 600</option><option value="700">粗体 700</option><option value="800">特粗 800</option><option value="900">黑体 900</option></select><input data-field="color" aria-label="文字颜色" type="color" /><details class="shadow-control"><summary>柔和阴影</summary><label>颜色<input data-field="shadow_color" aria-label="阴影颜色" type="color" /></label><label>X<input data-field="shadow_offset_x" aria-label="阴影 X 偏移" type="number" min="-40" max="40" step="1" /></label><label>Y<input data-field="shadow_offset_y" aria-label="阴影 Y 偏移" type="number" min="-40" max="40" step="1" /></label><label>模糊<input data-field="shadow_blur" aria-label="阴影模糊" type="number" min="0" max="12" step="0.5" /></label><label>不透明度<input data-field="shadow_opacity" aria-label="阴影不透明度" type="number" min="0" max="255" step="1" /></label></details><button class="remove-text secondary small" type="button" title="删除本行">×</button>`;
  row.querySelector('[data-field="text"]').value = config.text || '';
  row.querySelector('[data-field="x"]').value = config.x ?? 0;
  row.querySelector('[data-field="y"]').value = config.y ?? 0;
  row.querySelector('[data-field="size"]').value = config.size ?? 0.03;
  row.querySelector('[data-field="color"]').value = config.color || '#ffffff';
  row.querySelector('[data-field="font_family"]').value = config.font_family || '';
  row.querySelector('[data-field="font_weight"]').value = String(config.font_weight ?? (config.bold ? 700 : TEXT_STYLE_DEFAULTS.font_weight));
  row.querySelector('[data-field="shadow_color"]').value = config.shadow_color || TEXT_STYLE_DEFAULTS.shadow_color;
  row.querySelector('[data-field="shadow_offset_x"]').value = config.shadow_offset_x ?? TEXT_STYLE_DEFAULTS.shadow_offset_x;
  row.querySelector('[data-field="shadow_offset_y"]').value = config.shadow_offset_y ?? TEXT_STYLE_DEFAULTS.shadow_offset_y;
  row.querySelector('[data-field="shadow_blur"]').value = config.shadow_blur ?? TEXT_STYLE_DEFAULTS.shadow_blur;
  row.querySelector('[data-field="shadow_opacity"]').value = config.shadow_opacity ?? TEXT_STYLE_DEFAULTS.shadow_opacity;
  row.querySelector('.remove-text').addEventListener('click', () => row.remove());
  container.appendChild(row);
}
function buildTextRows(type, values = {}) {
  const defaults = type === 'checkin' ? CHECKIN_TEXTS : STATUS_TEXTS;
  const container = $(`#${type}-text-rows`); container.innerHTML = '';
  const keys = [...Object.keys(defaults), ...Object.keys(values || {}).filter((key) => !(key in defaults))];
  keys.forEach((key) => textRow(container, key, { ...TEXT_STYLE_DEFAULTS, ...(defaults[key] || { label: key, text: '', x: 0.08, y: 0.72, size: 0.03, color: '#ffffff', bold: false }), ...(values?.[key] || {}) }, defaults[key]?.label || key));
}
function readTextRows(type) {
  const texts = {};
  $$(`#${type}-text-rows .text-row`).forEach((row) => {
    const key = row.dataset.textKey; if (!key) return;
    const field = (name) => row.querySelector(`[data-field="${name}"]`);
    const fontWeight = numberValue(field('font_weight').value, 400);
    texts[key] = {
      text: field('text').value.trim(), x: numberValue(field('x').value, 0), y: numberValue(field('y').value, 0), size: numberValue(field('size').value, 0.03), color: field('color').value,
      font_family: field('font_family').value, font_weight: fontWeight, bold: fontWeight >= 600,
      shadow_color: field('shadow_color').value, shadow_offset_x: numberValue(field('shadow_offset_x').value, 0), shadow_offset_y: numberValue(field('shadow_offset_y').value, 2), shadow_blur: numberValue(field('shadow_blur').value, 2.5), shadow_opacity: numberValue(field('shadow_opacity').value, 64),
    };
  });
  return texts;
}
function renderTemplateList(type) {
  const list = type === 'checkin' ? checkinTemplates : statusTemplates;
  const selected = type === 'checkin' ? selectedCheckinId : selectedStatusId;
  const element = $(`#${type}-template-list`); element.innerHTML = '';
  list.forEach((template) => {
    const item = document.createElement('button'); item.type = 'button'; item.className = `character-item ${template.id === selected ? 'active' : ''}`;
    const binding = template.bound_entry_id ? (characters.find((entry) => entry.id === template.bound_entry_id)?.name || '已删除绑定') : '通用';
    item.innerHTML = `<img src="${template.preview || assetUrl(template.background_image || template.image, type === 'checkin' ? 'checkin-assets' : 'status-assets')}" alt="" /><span><strong>${escapeHtml(template.name || template.id)}</strong><span>${escapeHtml(binding)} · ${template.enabled ? '已启用' : '已停用'}</span></span>`;
    item.addEventListener('click', () => { if (type === 'checkin') selectedCheckinId = template.id; else selectedStatusId = template.id; renderTemplateList(type); fillTemplate(type, template); });
    element.appendChild(item);
  });
  if (!element.childElementCount) element.innerHTML = '<p class="empty">暂无模板。</p>';
}
function fillTemplate(type, template) {
  const form = $(`#${type}-template-form`); const data = template || templateDefaults(type);
  setValue(form, 'id', data.id); setValue(form, 'name', data.name); setValue(form, 'bound_entry_id', data.bound_entry_id || ''); setValue(form, 'priority', data.priority ?? 0); setValue(form, 'font_family', data.font_family || 'default');
  setValue(form, 'background_image', data.background_image || data.image || ''); setValue(form, 'panel_image', data.panel_image || ''); setValue(form, 'portrait_frame_image', data.portrait_frame_image || ''); setValue(form, 'panel_color', data.panel_color || (type === 'checkin' ? '#152238' : '#ffffff'));
  setChecked(form, 'enabled', data.enabled !== false); setChecked(form, 'show_companion', data.show_companion !== false); setValue(form, 'portrait_scale', data.portrait_scale ?? 1); setValue(form, 'portrait_offset_x', data.portrait_offset_x ?? 0); setValue(form, 'portrait_offset_y', data.portrait_offset_y ?? 0);
  if (form.elements.message) setValue(form, 'message', data.message || '');
  buildTextRows(type, data.texts || {});
  const preview = $(`#${type}-preview`); const assetType = type === 'checkin' ? 'checkin-assets' : 'status-assets'; preview.src = data.preview || assetUrl(data.background_image || data.image, assetType);
  schedulePreview(type);
}
function readTemplate(type) {
  const form = $(`#${type}-template-form`);
  return {
    id: form.elements.id.value.trim(), name: form.elements.name.value.trim(), bound_entry_id: form.elements.bound_entry_id.value, priority: numberValue(form.elements.priority.value, 0), font_family: form.elements.font_family.value, text_style_version: 2,
    background_image: form.elements.background_image.value.trim(), panel_image: form.elements.panel_image.value.trim(), portrait_frame_image: form.elements.portrait_frame_image.value.trim(), panel_color: form.elements.panel_color.value,
    enabled: form.elements.enabled.checked, show_companion: form.elements.show_companion.checked, portrait_scale: numberValue(form.elements.portrait_scale.value, 1), portrait_offset_x: numberValue(form.elements.portrait_offset_x.value, 0), portrait_offset_y: numberValue(form.elements.portrait_offset_y.value, 0),
    ...(type === 'checkin' ? { message: form.elements.message.value.trim() } : {}), texts: readTextRows(type),
  };
}
function schedulePreview(type) {
  const timer = type === 'checkin' ? checkinPreviewTimer : statusPreviewTimer;
  window.clearTimeout(timer);
  const id = window.setTimeout(() => safely(() => updateTemplatePreview(type, true)), 450);
  if (type === 'checkin') checkinPreviewTimer = id; else statusPreviewTimer = id;
}
async function updateTemplatePreview(type, quiet = false) {
  const result = normalizeResponse(await apiPost(`/${type}-templates/preview`, readTemplate(type)));
  if (!result.preview) throw new Error('后台没有返回预览图片。');
  $(`#${type}-preview`).src = result.preview;
  if (!quiet) toast(`已生成${type === 'checkin' ? '打卡' : '状态栏'}预览。`);
}
async function uploadTemplateLayer(type, field, file) {
  if (!file?.type?.startsWith('image/')) { toast('请粘贴或选择真实图片文件。'); return; }
  const result = normalizeResponse(await upload(type === 'checkin' ? '/upload-checkin-image' : '/upload-status-image', file));
  if (!result.image) throw new Error('模板图片上传失败。');
  $(`#${type}-template-form`).elements[field].value = result.image;
  await updateTemplatePreview(type, true); toast('模板图片已上传。');
}
function addCustomText(type) {
  const key = window.prompt('请输入文字字段 ID（英文、数字或下划线，例如 event）：', 'custom_text');
  if (!key) return;
  const safe = key.trim().replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_+|_+$/g, '').slice(0, 40);
  if (!safe) { toast('字段 ID 无效。'); return; }
  if ($(`#${type}-text-rows .text-row[data-text-key="${safe}"]`)) { toast('该文字行已存在。'); return; }
  textRow($(`#${type}-text-rows`), safe, { ...TEXT_STYLE_DEFAULTS, label: safe, text: '', x: 0.08, y: 0.72, size: 0.03, color: '#ffffff', bold: false }, safe);
  schedulePreview(type);
}

function assetPayload() {
  return { scope_id: $('#asset-scope').value.trim(), user_id: $('#asset-user').value.trim(), name: $('#asset-name').value.trim() };
}
function bindEvents() {
  $('#refresh').addEventListener('click', () => safely(loadAll));
  $$('.type-filter button').forEach((button) => button.addEventListener('click', () => {
    selectedFilter = button.dataset.filter; $$('.type-filter button').forEach((entry) => entry.classList.toggle('active', entry === button)); renderList();
  }));
  $$('.color-tabs button').forEach((button) => button.addEventListener('click', () => {
    $$('.color-tabs button').forEach((entry) => entry.classList.toggle('active', entry === button)); renderColorGroup();
  }));
  $('#save-settings').addEventListener('click', () => safely(async () => {
    const result = normalizeResponse(await apiPost('/settings', readSettings())); settings = result.settings || settings; toast('视觉色彩已保存。');
  }));
  $('#character-form').elements.kind.addEventListener('change', (event) => toggleKindFields(event.target.value));
  $('#new-character').addEventListener('click', () => {
    selectedId = ''; const form = $('#character-form'); form.reset(); form.elements.kind.value = 'companion'; form.elements.quality.value = 'SR'; form.elements.focal_x.value = '0.5'; form.elements.focal_y.value = '0.5'; form.elements.exp_amount.value = '10'; form.elements.draw_weight.value = '10';
    toggleKindFields('companion'); $('#preview-image').removeAttribute('src'); $('#preview-title').textContent = '新增条目'; $('#preview-subtitle').textContent = '填写资料后上传图片；可调画面焦点。'; renderList();
  });
  $('#save-button').addEventListener('click', () => safely(async () => {
    const data = readCharacter(); if (!data.id || !data.name) { toast('ID 和中文名称必填。'); return; } if (data.kind === 'skin' && !data.parent_id) { toast('皮肤必须选择所属同伴。'); return; }
    $('#save-state').textContent = '保存中…'; const result = normalizeResponse(await apiPost('/characters', data)); $('#save-state').textContent = ''; selectedId = result.character?.id || data.id; toast('已保存条目。'); await loadAll();
  }));
  $('#delete-button').addEventListener('click', () => safely(async () => {
    const id = $('#character-form').elements.id.value.trim(); if (!id || !confirmDelete($('#delete-button'), `删除总库条目 ${id}`)) return; await apiDelete(`/characters/${id}`); selectedId = ''; toast('已删除总库条目。'); await loadAll();
  }));
  bindImageDropzone('#image-dropzone', '#image-upload', uploadEntryFile, 'pasted-entry.png');

  $('#known-player').addEventListener('change', (event) => {
    const player = players[Number(event.target.value)]; if (!player) return; $('#asset-scope').value = player.scope_id; $('#asset-user').value = player.user_id; $('#asset-name').value = player.name;
  });
  $('#grant-button').addEventListener('click', () => safely(async () => {
    const payload = { ...assetPayload(), character_id: $('#asset-character').value }; if (!payload.scope_id || !payload.user_id || !payload.character_id) { toast('请填写群/会话、用户和条目。'); return; }
    const result = normalizeResponse(await apiPost('/grant', payload)); toast(result.created ? '已发放条目。' : '玩家已拥有该条目。'); await loadAll();
  }));
  $('#revoke-button').addEventListener('click', () => safely(async () => {
    const payload = { ...assetPayload(), character_id: $('#asset-character').value, amount: numberValue($('#asset-amount').value, 1) }; if (!payload.scope_id || !payload.user_id || !payload.character_id) { toast('请填写群/会话、用户和条目。'); return; }
    if (!confirmDelete($('#revoke-button'), '扣除玩家资产')) return;
    const result = normalizeResponse(await apiPost('/revoke', payload)); toast(`已扣除，剩余：${result.result?.remaining ?? 0}`); await loadAll();
  }));
  $('#grant-exclusive-button').addEventListener('click', () => safely(async () => {
    const select = $('#grant-exclusive'); const option = select.options[select.selectedIndex]; const payload = { ...assetPayload(), companion_id: select.value, exclusive_name: option?.dataset.exclusiveName || '' };
    if (!payload.scope_id || !payload.user_id || !payload.companion_id || !payload.exclusive_name) { toast('请填写群/用户并选择专属物品。'); return; }
    await apiPost('/grant-exclusive', payload); toast('已发放专属物品。'); await loadAll();
  }));

  ['checkin', 'status'].forEach((type) => {
    $(`#new-${type}-template`).addEventListener('click', () => { if (type === 'checkin') selectedCheckinId = ''; else selectedStatusId = ''; fillTemplate(type, templateDefaults(type)); renderTemplateList(type); });
    const form = $(`#${type}-template-form`); form.addEventListener('input', () => schedulePreview(type)); form.addEventListener('change', () => schedulePreview(type));
    $(`#preview-${type}-template`).addEventListener('click', () => safely(() => updateTemplatePreview(type, false)));
    $(`#save-${type}-template`).addEventListener('click', () => safely(async () => {
      const template = readTemplate(type); if (!template.id || !template.name) { toast('模板 ID 和名称必填。'); return; }
      const result = normalizeResponse(await apiPost(`/${type}-templates`, template)); if (type === 'checkin') selectedCheckinId = result.template?.id || template.id; else selectedStatusId = result.template?.id || template.id;
      toast(`已保存${type === 'checkin' ? '打卡' : '状态栏'}模板。`); await loadAll();
    }));
    $(`#delete-${type}-template`).addEventListener('click', () => safely(async () => {
      const id = form.elements.id.value.trim(); const button = $(`#delete-${type}-template`); if (!id || !confirmDelete(button, `删除${type === 'checkin' ? '打卡' : '状态栏'}模板 ${id}`)) return;
      await apiDelete(`/${type}-templates/${id}`); if (type === 'checkin') selectedCheckinId = ''; else selectedStatusId = ''; toast('已删除模板。'); await loadAll();
    }));
    $(`#add-${type}-text`).addEventListener('click', () => addCustomText(type));
    ['background_image', 'panel_image', 'portrait_frame_image'].forEach((field, index) => {
      const suffix = ['background', 'panel', 'frame'][index];
      bindImageDropzone(`#${type}-${suffix}-dropzone`, `#${type}-${suffix}-upload`, (file) => uploadTemplateLayer(type, field, file), `pasted-${type}-${suffix}.png`);
    });
  });
}

async function boot() {
  if (bridge().ready) await bridge().ready();
  buildTextRows('checkin', CHECKIN_TEXTS); buildTextRows('status', STATUS_TEXTS); bindEvents(); await loadAll();
}
boot().catch((error) => { console.error(error); toast(errorText(error)); });
window.addEventListener('unhandledrejection', (event) => { console.error(event.reason); toast(errorText(event.reason)); });

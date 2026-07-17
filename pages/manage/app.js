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
  skill_2_name: { label: '2星技能名（绑定）', text: '2星 {skill_2_name}', x: 0.457, y: 0.53, size: 0.02, color: '#ffffff', bold: true },
  skill_2_desc: { label: '2星技能描述（绑定）', text: '{skill_2_desc}', x: 0.457, y: 0.573, size: 0.018, color: '#6d9bc6', bold: false },
  skill_3_name: { label: '3星技能名（绑定）', text: '3星 {skill_3_name}', x: 0.457, y: 0.606, size: 0.02, color: '#ffffff', bold: true },
  skill_3_desc: { label: '3星技能描述（绑定）', text: '{skill_3_desc}', x: 0.457, y: 0.649, size: 0.018, color: '#6d9bc6', bold: false },
  skill_5_name: { label: '5星技能名（绑定）', text: '5星 {skill_5_name}', x: 0.457, y: 0.682, size: 0.02, color: '#ffffff', bold: true },
  skill_5_desc: { label: '5星技能描述（绑定）', text: '{skill_5_desc}', x: 0.457, y: 0.725, size: 0.018, color: '#6d9bc6', bold: false },
};
const FONT_OPTIONS = [
  ['inherit', '跟随模板字体'],
  ['default', '默认中文字体'],
  ['msyh', '微软雅黑'],
  ['msyh_light', '微软雅黑细体'],
  ['deng', '等线'],
  ['simhei', '黑体'],
  ['simsun', '宋体'],
  ['kaiti', '楷体'],
  ['cute', '圆润可爱'],
  ['comic', '手写卡通'],
];
const TEXT_WEIGHT_OPTIONS = [['regular', '常规'], ['bold', '粗'], ['heavy', '特粗']];

let characters = [];
let players = [];
let settings = {};
let checkinTemplates = [];
let statusTemplates = [];
let miningTemplates = [];
let drawDesign = {};
let checkinAssets = [];
let statusAssets = [];
let selectedId = '';
let selectedCheckinId = '';
let selectedStatusId = '';
let selectedMiningId = '';
let selectedFilter = 'all';
let activeImagePasteHandler = null;
let checkinPreviewTimer = 0;
let statusPreviewTimer = 0;
let miningBackgrounds = [];
const templatePreviewVersion = { checkin: 0, status: 0 };

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
  checkinAssets = payload.checkin_assets || [];
  statusAssets = payload.status_assets || [];
  miningTemplates = payload.mining_templates || [];
  drawDesign = payload.draw_design || drawDesign;
  if (!selectedId && characters[0]) selectedId = characters[0].id;
  if (!selectedCheckinId && checkinTemplates[0]) selectedCheckinId = checkinTemplates[0].id;
  if (!selectedStatusId && statusTemplates[0]) selectedStatusId = statusTemplates[0].id;
  if (!selectedMiningId && miningTemplates[0]) selectedMiningId = miningTemplates[0].id;
  renderColorGroup(); renderList(); renderParentOptions(); renderBoundOptions(); renderPlayerOptions(); renderAssetOptions(); fillSettings();
  fillCharacter(characters.find((entry) => entry.id === selectedId) || characters[0]);
  renderTemplateList('checkin'); fillTemplate('checkin', checkinTemplates.find((entry) => entry.id === selectedCheckinId) || checkinTemplates[0]);
  renderTemplateList('status'); fillTemplate('status', statusTemplates.find((entry) => entry.id === selectedStatusId) || statusTemplates[0]);
  renderMiningTemplateList(); fillMiningTemplate(miningTemplates.find((entry) => entry.id === selectedMiningId) || miningTemplates[0]);
  fillDrawDesign(drawDesign);
  renderTemplateAssetList('checkin'); renderTemplateAssetList('status');
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
        ? `${entry.quality || '未标注品质'} · 抽取 ${entry.draw_weight || 1}${entry.in_pool ? ' · 奖池' : ''}${entry.mining_pool ? ` · 挖矿 ${entry.mining_weight || 1}` : ''}`
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
  $$('.profile-only').forEach((element) => element.classList.toggle('hidden', !['companion', 'skin'].includes(kind)));
  $$('.skin-only').forEach((element) => element.classList.toggle('hidden', kind !== 'skin'));
  $$('.item-only').forEach((element) => element.classList.toggle('hidden', kind !== 'item'));
  $$('.experience-only').forEach((element) => element.classList.toggle('hidden', kind !== 'experience_ball'));
  $$('.draw-weight').forEach((element) => element.classList.toggle('hidden', !['item', 'experience_ball'].includes(kind)));
  const form = $('#character-form');
  form.elements.quality.placeholder = kind === 'item' ? '普通 / 中级 / 高级（仅展示）' : (kind === 'experience_ball' ? '经验球' : 'SSR / SR / R');
}
function fillCharacter(entry) {
  const form = $('#character-form');
  if (!entry) { form.reset(); toggleKindFields('companion'); return; }
  selectedId = entry.id;
  setValue(form, 'kind', entry.kind || 'companion'); setValue(form, 'id', entry.id); setValue(form, 'name', entry.name); setValue(form, 'english_name', entry.english_name || entry.skin || '');
  setValue(form, 'quality', entry.quality || entry.star || 'R'); setValue(form, 'parent_id', entry.parent_id || ''); setValue(form, 'exclusive_items', exclusiveItemNames(entry).join('\n'));
  setValue(form, 'route', entry.route || ''); setValue(form, 'bonus', entry.bonus || ''); setValue(form, 'intro', entry.intro || ''); setValue(form, 'effect', entry.effect || ''); setValue(form, 'image', entry.image || '');
  setValue(form, 'focal_x', entry.focal_x ?? 0.5); setValue(form, 'focal_y', entry.focal_y ?? 0.5); setValue(form, 'exp_amount', entry.exp_amount ?? 10); setValue(form, 'draw_weight', entry.draw_weight ?? 10); setValue(form, 'mining_weight', entry.mining_weight ?? 10); setChecked(form, 'mining_pool', entry.mining_pool); setChecked(form, 'in_pool', entry.in_pool);
  const skills = entry.skills || []; [0, 1, 2].forEach((index) => { setValue(form, `skill${index}`, skills[index]?.[0] || ''); setValue(form, `skill${index}Desc`, skills[index]?.[1] || ''); });
  $('#parent-companion').value = entry.parent_id || '';
  toggleKindFields(entry.kind || 'companion');
  $('#preview-image').src = entry.preview || assetUrl(entry.image); $('#preview-title').textContent = entry.name || '未命名条目';
  $('#preview-subtitle').textContent = entry.kind === 'experience_ball'
    ? `抽中后直接 +${entry.exp_amount || 0} EXP，权重 ${entry.draw_weight || 1}`
    : entry.kind === 'item'
      ? `${kindLabel(entry.kind)} · ${entry.quality || '未标注品质'} · 抽取权重 ${entry.draw_weight || 1}`
      : `${kindLabel(entry.kind)} · ${entry.english_name || entry.quality || '—'}`;
}
function readCharacter() {
  const form = $('#character-form'); const kind = form.elements.kind.value;
  return {
    id: form.elements.id.value.trim(), kind, name: form.elements.name.value.trim(), english_name: form.elements.english_name.value.trim(), quality: form.elements.quality.value.trim(), parent_id: form.elements.parent_id.value,
    exclusive_items: form.elements.exclusive_items.value.trim(), route: form.elements.route.value.trim(), bonus: form.elements.bonus.value.trim(), intro: form.elements.intro.value.trim(), effect: form.elements.effect.value.trim(), image: form.elements.image.value.trim(), in_pool: form.elements.in_pool.checked,
    focal_x: numberValue(form.elements.focal_x.value, 0.5), focal_y: numberValue(form.elements.focal_y.value, 0.5), exp_amount: numberValue(form.elements.exp_amount.value, 10), draw_weight: numberValue(form.elements.draw_weight.value, 10), mining_pool: form.elements.mining_pool.checked, mining_weight: numberValue(form.elements.mining_weight.value, 10),
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
  const dispatchFiles = (files) => {
    const selected = [...(files || [])].filter(Boolean);
    return handler(input.multiple ? selected : selected[0]);
  };
  input.addEventListener('change', () => safely(() => dispatchFiles(input.files)));
  zone.addEventListener('focus', () => { activeImagePasteHandler = handler; });
  zone.addEventListener('click', () => { activeImagePasteHandler = handler; zone.focus(); input.click(); });
  zone.addEventListener('dragover', (event) => { event.preventDefault(); zone.classList.add('dragging'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragging'));
  zone.addEventListener('drop', (event) => { event.preventDefault(); zone.classList.remove('dragging'); safely(() => dispatchFiles(event.dataTransfer.files)); });
  zone.addEventListener('paste', (event) => {
    const item = [...(event.clipboardData?.items || [])].find((candidate) => candidate.type?.startsWith('image/'));
    if (!item) { toast('剪贴板中没有真实图片文件。'); return; }
    event.preventDefault(); safely(() => dispatchFiles([blobAsFile(item.getAsFile(), fallbackName)]));
  });
  document.addEventListener('paste', (event) => {
    if (event.defaultPrevented || activeImagePasteHandler !== handler) return;
    const item = [...(event.clipboardData?.items || [])].find((candidate) => candidate.type?.startsWith('image/'));
    if (!item) return;
    event.preventDefault(); safely(() => dispatchFiles([blobAsFile(item.getAsFile(), fallbackName)]));
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
    id: '', name: '', bound_entry_id: '', priority: 0, background_image: '', image: '', enabled: true, font_family: 'default',
    ...(type === 'checkin' ? { messages: ['今日也要和同伴一起前进。', '线索会回应认真观察的人。', '和同伴一起，继续推进故事。', '今天的选择，也会留下新的线索。', '下一次相遇，或许就在转角。'] } : {}),
    ...(type === 'status' ? { progress: { enabled: true, x: 0.441, y: 0.440, width: 0.455, height: 0.043, background_color: '#dbe2ef', color: '' } } : {}),
    texts: Object.fromEntries(Object.entries(texts).map(([key, value]) => [key, { ...value }])),
  };
}
function textRow(container, key, config, label = '') {
  const row = document.createElement('div'); row.className = 'text-row'; row.dataset.textKey = key;
  const selectedFont = FONT_OPTIONS.some(([value]) => value === config.font_family) ? config.font_family : 'inherit';
  const fontOptions = FONT_OPTIONS.map(([value, text]) => `<option value="${value}"${value === selectedFont ? ' selected' : ''}>${text}</option>`).join('');
  const selectedWeight = TEXT_WEIGHT_OPTIONS.some(([value]) => value === config.weight)
    ? config.weight : (config.bold ? 'bold' : 'regular');
  const weightOptions = TEXT_WEIGHT_OPTIONS.map(([value, text]) => `<option value="${value}"${value === selectedWeight ? ' selected' : ''}>${text}</option>`).join('');
  row.innerHTML = `<strong>${escapeHtml(label || config.label || key)}</strong><input data-field="text" /><input data-field="x" type="number" min="0" max="1" step="0.01" /><input data-field="y" type="number" min="0" max="1" step="0.01" /><input data-field="size" type="number" min="0.015" max="0.15" step="0.005" /><select data-field="font_family">${fontOptions}</select><input data-field="color" type="color" /><select data-field="weight">${weightOptions}</select><label class="shadow-control"><input data-field="shadow" type="checkbox" /><span>阴影</span></label><button class="remove-text secondary small" type="button" title="删除本行">×</button>`;
  row.querySelector('[data-field="text"]').value = config.text || '';
  row.querySelector('[data-field="x"]').value = config.x ?? 0;
  row.querySelector('[data-field="y"]').value = config.y ?? 0;
  row.querySelector('[data-field="size"]').value = config.size ?? 0.03;
  row.querySelector('[data-field="color"]').value = config.color || '#ffffff';
  row.querySelector('[data-field="shadow"]').checked = config.shadow !== false;
  row.querySelector('.remove-text').addEventListener('click', () => {
    row.remove();
    // Deletion is part of the live template state.  Refresh the shared
    // renderer just like edits do, so the operator can confirm immediately
    // that the line is gone before saving the template.
    const type = container.id.replace(/-text-rows$/, '');
    if (type === 'checkin' || type === 'status') schedulePreview(type);
  });
  container.appendChild(row);
}
function buildTextRows(type, values = {}) {
  const defaults = type === 'checkin' ? CHECKIN_TEXTS : STATUS_TEXTS;
  const container = $(`#${type}-text-rows`); container.innerHTML = '';
  const hasSavedRows = values && typeof values === 'object';
  const keys = hasSavedRows ? Object.keys(values) : Object.keys(defaults);
  keys.forEach((key) => textRow(container, key, { ...(defaults[key] || { label: key, text: '', x: 0.08, y: 0.72, size: 0.03, color: '#ffffff', bold: false }), ...(values?.[key] || {}) }, defaults[key]?.label || key));
}
function readTextRows(type) {
  const texts = {};
  $$(`#${type}-text-rows .text-row`).forEach((row) => {
    const key = row.dataset.textKey; if (!key) return;
    const field = (name) => row.querySelector(`[data-field="${name}"]`);
    const weight = field('weight').value;
    texts[key] = { text: field('text').value.trim(), x: numberValue(field('x').value, 0), y: numberValue(field('y').value, 0), size: numberValue(field('size').value, 0.03), font_family: field('font_family').value, color: field('color').value, weight, bold: weight !== 'regular', shadow: field('shadow').checked };
  });
  return texts;
}
function renderTemplateList(type) {
  const list = type === 'checkin' ? checkinTemplates : statusTemplates;
  const selected = type === 'checkin' ? selectedCheckinId : selectedStatusId;
  const element = $(`#${type}-template-list`); element.innerHTML = '';
  const heading = document.createElement('div'); heading.className = 'list-heading'; heading.textContent = '模板（可滚动）'; element.appendChild(heading);
  list.forEach((template) => {
    const item = document.createElement('button'); item.type = 'button'; item.className = `character-item ${template.id === selected ? 'active' : ''}`;
    const binding = template.bound_entry_id ? (characters.find((entry) => entry.id === template.bound_entry_id)?.name || '已删除绑定') : '通用';
    const filename = template.background_image || template.image || '尚未上传背景';
    item.innerHTML = `<img src="${template.preview || assetUrl(filename, type === 'checkin' ? 'checkin-assets' : 'status-assets')}" alt="" /><span><strong>${escapeHtml(template.name || template.id)}</strong><span>${escapeHtml(binding)} · ${template.enabled ? '已启用' : '已停用'}<br />背景：${escapeHtml(filename)}</span></span>`;
    item.addEventListener('click', () => { if (type === 'checkin') selectedCheckinId = template.id; else selectedStatusId = template.id; renderTemplateList(type); fillTemplate(type, template); });
    element.appendChild(item);
  });
  if (!element.childElementCount) element.innerHTML = '<p class="empty">暂无模板。</p>';
}
function renderTemplateAssetList(type) {
  const assets = type === 'checkin' ? checkinAssets : statusAssets;
  const element = $(`#${type}-asset-list`); const form = $(`#${type}-template-form`);
  // Background selection is now direct from the upload area.  Keep this
  // helper harmless for old embedded pages that still include a file list.
  if (!element || !form) return;
  const selectedFile = form.elements.background_image.value.trim(); element.innerHTML = '';
  if (!assets.length) {
    element.innerHTML = '<p class="empty">暂无背景文件。上传背景后会显示在这里。</p>';
    return;
  }
  assets.forEach((asset) => {
    const filename = String(asset.filename || ''); if (!filename) return;
    const item = document.createElement('button'); item.type = 'button';
    item.className = `asset-file-item ${filename === selectedFile ? 'active' : ''}`;
    const image = document.createElement('img'); image.src = asset.preview || ''; image.alt = '';
    const copy = document.createElement('span'); const name = document.createElement('strong'); const hint = document.createElement('span');
    name.textContent = filename; hint.textContent = filename === selectedFile ? '当前背景' : '点击设为当前背景'; copy.append(name, hint); item.append(image, copy);
    item.addEventListener('click', () => {
      form.elements.background_image.value = filename;
      $(`#${type}-preview`).src = asset.preview || '';
      renderTemplateAssetList(type); schedulePreview(type); toast('已选择背景文件，保存模板后生效。');
    });
    element.appendChild(item);
  });
}
function fillTemplate(type, template) {
  const form = $(`#${type}-template-form`); const data = template || templateDefaults(type);
  setValue(form, 'id', data.id); setValue(form, 'name', data.name); setValue(form, 'bound_entry_id', data.bound_entry_id || ''); setValue(form, 'priority', data.priority ?? 0); setValue(form, 'font_family', data.font_family || 'default');
  setValue(form, 'background_image', data.background_image || data.image || '');
  setChecked(form, 'enabled', data.enabled !== false);
  if (type === 'status') {
    const progress = { ...templateDefaults('status').progress, ...(data.progress || {}) };
    setChecked(form, 'progress_enabled', progress.enabled !== false); setValue(form, 'progress_x', progress.x); setValue(form, 'progress_y', progress.y);
    setValue(form, 'progress_width', progress.width); setValue(form, 'progress_height', progress.height);
    setValue(form, 'progress_background_color', progress.background_color); setValue(form, 'progress_color', progress.color || '#6d9bc6');
    setChecked(form, 'progress_auto_color', !progress.color);
    [['progress_x', progress.x], ['progress_y', progress.y], ['progress_width', progress.width], ['progress_height', progress.height]].forEach(([name, value]) => {
      const slider = $(`[data-progress-for="${name}"]`); if (slider) slider.value = value;
    });
  }
  if (form.elements.messages) setValue(form, 'messages', (data.messages || []).join('\n'));
  buildTextRows(type, data.texts);
  const preview = $(`#${type}-preview`); const assetType = type === 'checkin' ? 'checkin-assets' : 'status-assets'; preview.src = data.preview || assetUrl(data.background_image || data.image, assetType);
  renderTemplateAssetList(type);
  schedulePreview(type);
}
function readTemplate(type) {
  const form = $(`#${type}-template-form`);
  return {
    id: form.elements.id.value.trim(), name: form.elements.name.value.trim(), bound_entry_id: form.elements.bound_entry_id.value, priority: numberValue(form.elements.priority.value, 0), font_family: form.elements.font_family.value,
    background_image: form.elements.background_image.value.trim(), enabled: form.elements.enabled.checked,
    ...(type === 'checkin' ? { messages: form.elements.messages.value.split(/\r?\n/).map((value) => value.trim()).filter(Boolean).slice(0, 5) } : {}),
    ...(type === 'status' ? { progress: { enabled: form.elements.progress_enabled.checked, x: numberValue(form.elements.progress_x.value, 0.441), y: numberValue(form.elements.progress_y.value, 0.440), width: numberValue(form.elements.progress_width.value, 0.455), height: numberValue(form.elements.progress_height.value, 0.043), background_color: form.elements.progress_background_color.value, color: form.elements.progress_auto_color.checked ? '' : form.elements.progress_color.value } } : {}),
    texts: readTextRows(type),
  };
}
function schedulePreview(type) {
  const timer = type === 'checkin' ? checkinPreviewTimer : statusPreviewTimer;
  window.clearTimeout(timer);
  const version = ++templatePreviewVersion[type];
  const id = window.setTimeout(() => safely(() => updateTemplatePreview(type, true, version)), 450);
  if (type === 'checkin') checkinPreviewTimer = id; else statusPreviewTimer = id;
}
async function updateTemplatePreview(type, quiet = false, version = null) {
  const requestVersion = version ?? ++templatePreviewVersion[type];
  const result = normalizeResponse(await apiPost(`/${type}-templates/preview`, readTemplate(type)));
  if (!result.preview) throw new Error('后台没有返回预览图片。');
  // A slower response from an earlier font/position edit must never overwrite
  // the current preview.  This was the reason controls looked ineffective.
  if (requestVersion !== templatePreviewVersion[type]) return;
  $(`#${type}-preview`).src = result.preview;
  if (!quiet) toast(`已生成${type === 'checkin' ? '打卡' : '状态栏'}预览。`);
}
async function uploadTemplateLayer(type, field, file) {
  if (!file?.type?.startsWith('image/')) { toast('请粘贴或选择真实图片文件。'); return; }
  const result = normalizeResponse(await upload(type === 'checkin' ? '/upload-checkin-image' : '/upload-status-image', file));
  if (!result.image) throw new Error('模板图片上传失败。');
  $(`#${type}-template-form`).elements[field].value = result.image;
  const assets = type === 'checkin' ? checkinAssets : statusAssets;
  if (!assets.some((asset) => asset.filename === result.image)) assets.unshift({ filename: result.image, preview: URL.createObjectURL(file) });
  renderTemplateAssetList(type);
  await updateTemplatePreview(type, true); toast('模板图片已上传。');
}
function addCustomText(type) {
  let serial = 1; let safe = 'custom_text';
  while ($(`#${type}-text-rows .text-row[data-text-key="${safe}"]`)) { serial += 1; safe = `custom_text_${serial}`; }
  // Do not depend on window.prompt: it is commonly disabled in the plugin
  // page iframe, which made the original add action appear to do nothing.
  textRow($(`#${type}-text-rows`), safe, { label: '自定义文字', text: '', x: 0.08, y: 0.72, size: 0.03, color: '#ffffff', weight: 'regular', shadow: true }, '自定义文字');
  schedulePreview(type);
}
function addPresetText(type) {
  const select = $(`#${type}-preset-text`); const key = select?.value;
  const defaults = type === 'status' ? STATUS_TEXTS : CHECKIN_TEXTS;
  if (!key || !defaults[key]) { toast('请选择可添加的预设字段。'); return; }
  if ($(`#${type}-text-rows .text-row[data-text-key="${key}"]`)) { toast('该预设字段已在文字列表中。'); return; }
  textRow($(`#${type}-text-rows`), key, { ...defaults[key] }, defaults[key].label || key);
  schedulePreview(type);
}

function bindProgressControls(type) {
  if (type !== 'status') return;
  const form = $(`#${type}-template-form`);
  $$(`[data-progress-for]`).forEach((slider) => {
    const field = form.elements[slider.dataset.progressFor];
    if (!field) return;
    slider.addEventListener('input', () => { field.value = slider.value; schedulePreview(type); });
    field.addEventListener('input', () => { slider.value = field.value; });
  });
}

function miningTemplateDefaults() {
  return { id: '', name: '', bound_entry_id: '', priority: 0, enabled: true, background_images: [] };
}
function renderMiningTemplateList() {
  const element = $('#mining-template-list'); element.innerHTML = '';
  const heading = document.createElement('div'); heading.className = 'list-heading'; heading.textContent = '模板（可滚动）'; element.appendChild(heading);
  miningTemplates.forEach((template) => {
    const item = document.createElement('button'); item.type = 'button'; item.className = `character-item ${template.id === selectedMiningId ? 'active' : ''}`;
    const binding = template.bound_entry_id ? (characters.find((entry) => entry.id === template.bound_entry_id)?.name || '已删除绑定') : '通用';
    const backgrounds = Array.isArray(template.background_images) ? template.background_images : [];
    const image = backgrounds[0] || '';
    item.innerHTML = `<img src="${assetUrl(image, 'mining-assets')}" alt="" /><span><strong>${escapeHtml(template.name || template.id)}</strong><span>${escapeHtml(binding)} · ${template.enabled ? '已启用' : '已停用'}<br />背景 ${backgrounds.length}/6</span></span>`;
    item.addEventListener('click', () => { selectedMiningId = template.id; renderMiningTemplateList(); fillMiningTemplate(template); });
    element.appendChild(item);
  });
  if (!miningTemplates.length) element.innerHTML = '<p class="empty">暂无挖矿模板。</p>';
}
function renderMiningBackgroundGallery() {
  const gallery = $('#mining-background-gallery'); gallery.innerHTML = '';
  miningBackgrounds.forEach((filename, index) => {
    const card = document.createElement('div'); card.className = 'background-card';
    card.innerHTML = `<img src="${assetUrl(filename, 'mining-assets')}" alt="挖矿背景 ${index + 1}" /><span title="${escapeHtml(filename)}">背景 ${index + 1}：${escapeHtml(filename)}</span><button class="danger small" type="button" title="从本模板移除">×</button>`;
    card.querySelector('button').addEventListener('click', () => {
      miningBackgrounds.splice(index, 1); renderMiningBackgroundGallery();
    });
    gallery.appendChild(card);
  });
}
function fillMiningTemplate(template) {
  const form = $('#mining-template-form'); const data = template || miningTemplateDefaults();
  selectedMiningId = data.id || '';
  setValue(form, 'id', data.id); setValue(form, 'name', data.name); setValue(form, 'bound_entry_id', data.bound_entry_id || ''); setValue(form, 'priority', data.priority ?? 0); setChecked(form, 'enabled', data.enabled !== false);
  miningBackgrounds = Array.isArray(data.background_images) ? data.background_images.slice(0, 6) : [];
  renderMiningBackgroundGallery();
}
function readMiningTemplate() {
  const form = $('#mining-template-form');
  return {
    id: form.elements.id.value.trim(), name: form.elements.name.value.trim(), bound_entry_id: form.elements.bound_entry_id.value,
    priority: numberValue(form.elements.priority.value, 0), enabled: form.elements.enabled.checked,
    background_images: miningBackgrounds.slice(0, 6),
  };
}
async function uploadMiningBackgrounds(files) {
  const selected = Array.isArray(files) ? files : [files];
  let uploaded = 0;
  for (const file of selected) {
    if (miningBackgrounds.length >= 6) { toast('每个挖矿模板最多保存 6 张背景。'); break; }
    if (!file?.type?.startsWith('image/')) { toast('请上传 PNG、JPG 或 WebP 图片。'); continue; }
    const result = normalizeResponse(await upload('/upload-mining-image', file));
    if (!result.image) throw new Error('挖矿背景上传失败。');
    miningBackgrounds.push(result.image); uploaded += 1;
  }
  renderMiningBackgroundGallery();
  if (uploaded) toast(`已加入 ${uploaded} 张挖矿背景；保存模板后生效。`);
}

function fillDrawDesign(design) {
  const form = $('#draw-design-form'); const data = design || {};
  setValue(form, 'background_image', data.background_image || '');
  setValue(form, 'result_border_color', data.result_border_color || '#e9f3ff');
  setValue(form, 'pity_border_color', data.pity_border_color || '#b8d5f1');
  const preview = $('#draw-design-preview');
  if (data.background_image) preview.src = assetUrl(data.background_image, 'draw-assets'); else preview.removeAttribute('src');
}
function readDrawDesign() {
  const form = $('#draw-design-form');
  return {
    background_image: form.elements.background_image.value.trim(),
    result_border_color: form.elements.result_border_color.value,
    pity_border_color: form.elements.pity_border_color.value,
  };
}
async function uploadDrawBackground(file) {
  if (!file?.type?.startsWith('image/')) { toast('请上传 PNG、JPG 或 WebP 图片。'); return; }
  const result = normalizeResponse(await upload('/upload-draw-image', file));
  if (!result.image) throw new Error('抽奖背景上传失败。');
  $('#draw-design-form').elements.background_image.value = result.image;
  $('#draw-design-preview').src = URL.createObjectURL(file);
  toast('抽奖背景已上传；保存抽奖设计后生效。');
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
  $('#character-form').elements.in_pool.addEventListener('change', () => safely(async () => {
    const form = $('#character-form'); const data = readCharacter();
    if (!data.id || !data.name) {
      form.elements.in_pool.checked = false;
      toast('请先填写并保存条目 ID 和名称，再加入奖池。');
      return;
    }
    const result = normalizeResponse(await apiPost('/characters', data));
    selectedId = result.character?.id || data.id;
    toast(data.in_pool ? '已加入本期奖池并保存。' : '已从本期奖池移除并保存。');
    await loadAll();
  }));
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
    const presetButton = $(`#add-${type}-preset-text`);
    if (presetButton) presetButton.addEventListener('click', () => addPresetText(type));
    bindProgressControls(type);
    bindImageDropzone(`#${type}-background-dropzone`, `#${type}-background-upload`, (file) => uploadTemplateLayer(type, 'background_image', file), `pasted-${type}-background.png`);
  });

  $('#new-mining-template').addEventListener('click', () => {
    selectedMiningId = ''; fillMiningTemplate(miningTemplateDefaults()); renderMiningTemplateList();
  });
  $('#save-mining-template').addEventListener('click', () => safely(async () => {
    const template = readMiningTemplate();
    if (!template.id || !template.name) { toast('挖矿模板 ID 和名称必填。'); return; }
    const result = normalizeResponse(await apiPost('/mining-templates', template));
    selectedMiningId = result.template?.id || template.id;
    toast('已保存挖矿模板。'); await loadAll();
  }));
  $('#delete-mining-template').addEventListener('click', () => safely(async () => {
    const form = $('#mining-template-form'); const id = form.elements.id.value.trim(); const button = $('#delete-mining-template');
    if (!id || !confirmDelete(button, `删除挖矿模板 ${id}`)) return;
    await apiDelete(`/mining-templates/${id}`); selectedMiningId = ''; toast('已删除挖矿模板。'); await loadAll();
  }));
  bindImageDropzone('#mining-background-dropzone', '#mining-background-upload', uploadMiningBackgrounds, 'pasted-mining-background.png');

  $('#save-draw-design').addEventListener('click', () => safely(async () => {
    const result = normalizeResponse(await apiPost('/draw-design', readDrawDesign()));
    drawDesign = result.draw_design || readDrawDesign(); fillDrawDesign(drawDesign); toast('已保存抽奖设计。');
  }));
  bindImageDropzone('#draw-background-dropzone', '#draw-background-upload', uploadDrawBackground, 'pasted-draw-background.png');
}

async function boot() {
  if (bridge().ready) await bridge().ready();
  buildTextRows('checkin', CHECKIN_TEXTS); buildTextRows('status', STATUS_TEXTS); bindEvents(); await loadAll();
}
boot().catch((error) => { console.error(error); toast(errorText(error)); });
window.addEventListener('unhandledrejection', (event) => { console.error(event.reason); toast(errorText(event.reason)); });

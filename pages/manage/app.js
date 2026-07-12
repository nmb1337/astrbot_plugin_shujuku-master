const PLUGIN = 'astrbot_plugin_juben_npc';
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];
const TEMPLATE_KEYS = ['title', 'reward', 'coins', 'message'];

let characters = [];
let players = [];
let settings = {};
let checkinTemplates = [];
let selectedId = '';
let selectedTemplateId = '';
let selectedFilter = 'all';
let activeImagePasteHandler = null;

const bridge = () => window.AstrBotPluginPage || {};
const endpoint = (path) => String(path || '').trim().replace(/^\/+/, '');

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
  return parseResponse(await fetch(`/api/plug/${encodeURIComponent(PLUGIN)}/${target}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }));
}

async function apiDelete(path) { return apiPost(`${path}/delete`, {}); }

async function upload(path, file) {
  const api = bridge(); const target = endpoint(path);
  let bridgeError = null;
  if (api.upload) {
    try { return await api.upload(target, file); }
    catch (error) { bridgeError = error; }
  }
  // AstrBot's ordinary JSON bridge is more reliable than multipart in some
  // desktop WebUI builds. Fall back for normal-sized images instead of
  // presenting the unhelpful browser-level “Network Error”.
  if (api.apiPost && file && file.size <= 10 * 1024 * 1024) {
    try {
      return await api.apiPost(`${target}/data-url`, {
        filename: file.name || 'upload.png',
        data_url: await fileAsDataUrl(file),
      });
    } catch (fallbackError) {
      throw new Error(fallbackError?.message || bridgeError?.message || '图片上传失败');
    }
  }
  if (bridgeError) throw bridgeError;
  const form = new FormData(); form.append('file', file);
  return parseResponse(await fetch(`/api/plug/${encodeURIComponent(PLUGIN)}/${target}`, { method: 'POST', body: form }));
}

function fileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('读取图片失败，请重新选择文件。'));
    reader.onload = () => resolve(String(reader.result || ''));
    reader.readAsDataURL(file);
  });
}

function normalizeResponse(result) { return result?.data || result || {}; }
function assetUrl(image, kind = 'assets') { return image ? `/api/plug/${PLUGIN}/${kind}/${encodeURIComponent(image)}` : ''; }
function escapeHtml(value) { return String(value ?? '').replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#039;'); }
function kindLabel(kind) { return ({ companion: '同伴', skin: '皮肤', item: '道具' })[kind] || '同伴'; }
function exclusiveItemNames(entry) {
  const raw = entry?.exclusive_items?.length ? entry.exclusive_items : (entry?.exclusive_item || '');
  const values = Array.isArray(raw) ? raw : String(raw).split(/[\r\n,，;；]+/);
  return [...new Set(values.map((value) => String(value?.name || value || '').trim()).filter(Boolean))];
}

function toast(message) {
  const el = $('#toast'); el.textContent = message; el.classList.add('show');
  window.setTimeout(() => el.classList.remove('show'), 2200);
}

function errorText(error) { return error?.message || '操作失败，请查看控制台'; }
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
  button.textContent = '再次点击确认删除';
  toast(`请在 5 秒内再次点击，确认删除${label}。`);
  button.dataset.confirmTimer = String(window.setTimeout(() => {
    button.textContent = button.dataset.defaultLabel || '删除';
    delete button.dataset.confirmUntil; delete button.dataset.confirmTimer;
  }, 5000));
  return false;
}

async function loadAll() {
  const payload = normalizeResponse(await apiGet('/characters'));
  characters = payload.characters || [];
  players = payload.players || [];
  settings = payload.settings || settings;
  checkinTemplates = payload.checkin_templates || [];
  if (!selectedId && characters[0]) selectedId = characters[0].id;
  if (!selectedTemplateId && checkinTemplates[0]) selectedTemplateId = checkinTemplates[0].id;
  renderList(); renderParentOptions(); renderPlayerOptions(); renderGrantOptions(); fillSettings();
  fillForm(characters.find((entry) => entry.id === selectedId) || characters[0]);
  renderTemplateList(); fillTemplate(checkinTemplates.find((entry) => entry.id === selectedTemplateId) || checkinTemplates[0]);
}

function renderList() {
  const list = $('#character-list'); list.innerHTML = '';
  const sorted = (entries) => [...entries].sort((a, b) => String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN'));
  const appendHeading = (text, muted = false) => {
    const heading = document.createElement('div'); heading.className = 'list-heading'; heading.textContent = text;
    if (muted) { heading.style.color = '#98a3b3'; heading.style.fontStyle = 'italic'; }
    list.appendChild(heading);
  };
  const appendEntry = (entry) => {
    const item = document.createElement('button'); item.type = 'button';
    item.className = `character-item ${entry.id === selectedId ? 'active' : ''} ${entry.kind === 'skin' ? 'skin-entry' : ''}`;
    item.innerHTML = `<img src="${entry.preview || assetUrl(entry.image)}" alt="" /><span><strong>${escapeHtml(entry.kind === 'skin' ? `↳ ${entry.name}` : entry.name)}</strong><span>${escapeHtml(entry.english_name || '—')} · ${escapeHtml(entry.quality || entry.star || 'R')} ${entry.in_pool ? '· 奖池' : ''}</span></span>`;
    item.addEventListener('click', () => { selectedId = entry.id; renderList(); fillForm(entry); }); list.appendChild(item);
  };
  const companions = sorted(characters.filter((entry) => entry.kind === 'companion'));
  const skins = characters.filter((entry) => entry.kind === 'skin');
  const items = sorted(characters.filter((entry) => entry.kind === 'item'));
  const skinsByParent = new Map();
  skins.forEach((skin) => {
    const parentId = skin.parent_id ? String(skin.parent_id) : '';
    if (!skinsByParent.has(parentId)) skinsByParent.set(parentId, []);
    skinsByParent.get(parentId).push(skin);
  });
  skinsByParent.forEach((group, parentId) => skinsByParent.set(parentId, sorted(group)));
  const parentIds = new Set(companions.map((entry) => String(entry.id)));
  const orphanSkins = [
    ...(skinsByParent.get('') || []),
    ...[...skinsByParent.entries()].filter(([parentId]) => parentId && !parentIds.has(parentId)).flatMap(([, group]) => group),
  ];
  const appendOrphans = () => {
    if (!orphanSkins.length) return;
    appendHeading('未关联同伴的皮肤（请在编辑页选择所属同伴）', true);
    sorted(orphanSkins).forEach(appendEntry);
  };

  if (selectedFilter === 'all') {
    if (companions.length || skins.length) appendHeading('同伴');
    companions.forEach((companion) => {
      appendEntry(companion);
      (skinsByParent.get(String(companion.id)) || []).forEach(appendEntry);
    });
    appendOrphans();
    if (items.length) { appendHeading(kindLabel('item')); items.forEach(appendEntry); }
  } else if (selectedFilter === 'skin') {
    companions.forEach((companion) => {
      const group = skinsByParent.get(String(companion.id)) || [];
      if (!group.length) return;
      appendHeading(`${companion.name} 的皮肤`, true);
      group.forEach(appendEntry);
    });
    appendOrphans();
  } else {
    const entries = selectedFilter === 'companion' ? companions : items;
    if (entries.length) { appendHeading(kindLabel(selectedFilter)); entries.forEach(appendEntry); }
  }
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

function renderPlayerOptions() {
  const select = $('#known-player'); select.innerHTML = '<option value="">手动填写</option>';
  players.forEach((player, index) => { const option = document.createElement('option'); option.value = String(index); option.textContent = `${player.name} / ${player.user_id} / ${player.scope_id}`; select.appendChild(option); });
}

function renderGrantOptions() {
  const select = $('#grant-character'); select.innerHTML = '';
  characters.forEach((entry) => { const option = document.createElement('option'); option.value = entry.id; option.textContent = `${kindLabel(entry.kind)} · ${entry.name} / ${entry.english_name || entry.quality || '—'}`; select.appendChild(option); });
  const exclusive = $('#grant-exclusive'); exclusive.innerHTML = '<option value="">选择要发放的专属物品</option>';
  characters.filter((entry) => entry.kind === 'companion').forEach((entry) => {
    exclusiveItemNames(entry).forEach((exclusiveName) => {
      const option = document.createElement('option'); option.value = entry.id; option.dataset.exclusiveName = exclusiveName;
      option.textContent = `${entry.name} · ${exclusiveName}`; exclusive.appendChild(option);
    });
  });
}

function setValue(form, name, value = '') { if (form.elements[name]) form.elements[name].value = value ?? ''; }
function setChecked(form, name, value = false) { if (form.elements[name]) form.elements[name].checked = Boolean(value); }

function toggleKindFields(kind) {
  $$('.companion-only').forEach((element) => element.classList.toggle('hidden', kind !== 'companion'));
  $$('.skin-only').forEach((element) => element.classList.toggle('hidden', kind !== 'skin'));
  $$('.item-only').forEach((element) => element.classList.toggle('hidden', kind !== 'item'));
  const quality = $('#character-form').elements.quality;
  quality.placeholder = kind === 'item' ? '普通 / 中级 / 高级' : 'SSR / SR / R';
}

function fillForm(entry) {
  const form = $('#character-form'); if (!entry) { form.reset(); toggleKindFields('companion'); return; }
  selectedId = entry.id; setValue(form, 'kind', entry.kind || 'companion'); setValue(form, 'id', entry.id); setValue(form, 'name', entry.name);
  setValue(form, 'english_name', entry.english_name || entry.skin || ''); setValue(form, 'quality', entry.quality || entry.star || 'R'); setValue(form, 'parent_id', entry.parent_id || ''); setValue(form, 'exclusive_items', exclusiveItemNames(entry).join('\n'));
  setValue(form, 'route', entry.route || ''); setValue(form, 'bonus', entry.bonus || ''); setValue(form, 'intro', entry.intro || ''); setValue(form, 'effect', entry.effect || ''); setValue(form, 'image', entry.image || ''); setValue(form, 'focal_x', entry.focal_x ?? 0.5); setValue(form, 'focal_y', entry.focal_y ?? 0.5); setChecked(form, 'in_pool', entry.in_pool);
  const skills = entry.skills || []; [0, 1, 2].forEach((index) => { setValue(form, `skill${index}`, skills[index]?.[0] || ''); setValue(form, `skill${index}Desc`, skills[index]?.[1] || ''); });
  $('#parent-companion').value = entry.parent_id || ''; toggleKindFields(entry.kind || 'companion');
  $('#preview-image').src = entry.preview || assetUrl(entry.image); $('#preview-title').textContent = entry.name || '未命名条目'; $('#preview-subtitle').textContent = `${kindLabel(entry.kind)} · ${entry.english_name || entry.quality || '—'} · 焦点 ${entry.focal_x ?? 0.5}/${entry.focal_y ?? 0.5}`;
}

function readForm() {
  const form = $('#character-form'); const kind = form.elements.kind.value;
  return {
    id: form.elements.id.value.trim(), kind, name: form.elements.name.value.trim(), english_name: form.elements.english_name.value.trim(), quality: form.elements.quality.value.trim(), parent_id: form.elements.parent_id.value,
    exclusive_items: form.elements.exclusive_items.value.trim(), route: form.elements.route.value.trim(), bonus: form.elements.bonus.value.trim(), intro: form.elements.intro.value.trim(), effect: form.elements.effect.value.trim(), image: form.elements.image.value.trim(), in_pool: form.elements.in_pool.checked,
    focal_x: Number(form.elements.focal_x.value), focal_y: Number(form.elements.focal_y.value),
    skills: [[form.elements.skill0.value.trim(), form.elements.skill0Desc.value.trim()], [form.elements.skill1.value.trim(), form.elements.skill1Desc.value.trim()], [form.elements.skill2.value.trim(), form.elements.skill2Desc.value.trim()]],
  };
}

async function uploadEntryFile(file) {
  if (!file?.type?.startsWith('image/')) { toast('请粘贴或选择真实图片文件；图片链接文字不能直接上传。'); return; }
  const result = normalizeResponse(await upload('/upload-image', file)); if (!result.image) throw new Error('图片上传失败');
  $('#character-form').elements.image.value = result.image; $('#preview-image').src = URL.createObjectURL(file); toast('图片已上传，保存条目后生效');
}

function blobAsFile(blob, fallback) {
  if (blob instanceof File) return blob;
  const extension = ({ 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/png': 'png' })[blob.type] || 'png';
  const name = fallback.replace(/\.[^.]+$/, `.${extension}`);
  return new File([blob], name, { type: blob.type || 'image/png' });
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
    if (!item) { toast('剪贴板中没有真实图片文件。'); return; }
    event.preventDefault(); safely(() => handler(blobAsFile(item.getAsFile(), fallbackName)));
  });
  document.addEventListener('focusin', (event) => { if (!zone.contains(event.target)) activeImagePasteHandler = null; });
}

function fillSettings() { const form = $('#settings-form'); Object.entries(settings).forEach(([key, value]) => { if (form.elements[key]) form.elements[key].value = value; }); }
function readSettings() { const form = $('#settings-form'); return Object.fromEntries($$('#settings-form input[type="color"]').map((input) => [input.name, input.value])); }

function templateField(key, field) { return $(`#checkin-template-form [name="${key}-${field}"]`); }
function newTemplate() { return { id: '', name: '', image: '', enabled: true, show_companion: true, message: '今日也要和同伴一起前进。', panel_color: '#152238', texts: {
  title: { text: '{title}', x: 0.07, y: 0.14, size: 0.062, color: '#ffffff', bold: true }, reward: { text: '{reward}', x: 0.08, y: 0.30, size: 0.042, color: '#eaf4ff', bold: true }, coins: { text: '当前星币：{coins}', x: 0.08, y: 0.41, size: 0.038, color: '#d7e6f5', bold: false }, message: { text: '{message}', x: 0.08, y: 0.58, size: 0.03, color: '#c8d9ea', bold: false },
} }; }

function renderTemplateList() {
  const list = $('#checkin-template-list'); list.innerHTML = '';
  checkinTemplates.forEach((template) => { const item = document.createElement('button'); item.type = 'button'; item.className = `character-item ${template.id === selectedTemplateId ? 'active' : ''}`; item.innerHTML = `<img src="${template.preview || assetUrl(template.image, 'checkin-assets')}" alt="" /><span><strong>${escapeHtml(template.name)}</strong><span>${template.enabled ? '已启用' : '已停用'} · ${template.show_companion ? '大同伴框' : '无角色框'}</span></span>`; item.addEventListener('click', () => { selectedTemplateId = template.id; renderTemplateList(); fillTemplate(template); }); list.appendChild(item); });
}

function fillTemplate(template) {
  const form = $('#checkin-template-form'); if (!template) { form.reset(); return; }
  setValue(form, 'id', template.id); setValue(form, 'name', template.name); setValue(form, 'image', template.image); setValue(form, 'message', template.message || ''); setValue(form, 'panel_color', template.panel_color || '#152238'); setChecked(form, 'enabled', template.enabled); setChecked(form, 'show_companion', template.show_companion !== false);
  TEMPLATE_KEYS.forEach((key) => { const text = template.texts?.[key] || newTemplate().texts[key]; templateField(key, 'text').value = text.text || ''; templateField(key, 'x').value = text.x ?? 0; templateField(key, 'y').value = text.y ?? 0; templateField(key, 'size').value = text.size ?? 0.04; templateField(key, 'color').value = text.color || '#ffffff'; templateField(key, 'bold').checked = Boolean(text.bold); });
  $('#checkin-preview').src = template.preview || assetUrl(template.image, 'checkin-assets'); scheduleCheckinPreview();
}

function readTemplate() { const form = $('#checkin-template-form'); const template = { id: form.elements.id.value.trim(), name: form.elements.name.value.trim(), image: form.elements.image.value.trim(), enabled: form.elements.enabled.checked, show_companion: form.elements.show_companion.checked, message: form.elements.message.value.trim(), panel_color: form.elements.panel_color.value, texts: {} }; TEMPLATE_KEYS.forEach((key) => { template.texts[key] = { text: templateField(key, 'text').value.trim(), x: Number(templateField(key, 'x').value), y: Number(templateField(key, 'y').value), size: Number(templateField(key, 'size').value), color: templateField(key, 'color').value, bold: templateField(key, 'bold').checked }; }); return template; }

let checkinPreviewTimer = 0;
function scheduleCheckinPreview() { window.clearTimeout(checkinPreviewTimer); checkinPreviewTimer = window.setTimeout(() => safely(() => updateCheckinPreview(true)), 400); }
async function updateCheckinPreview(quiet = false) { const result = normalizeResponse(await apiPost('/checkin-templates/preview', readTemplate())); if (!result.preview) throw new Error('后台没有返回预览图片'); $('#checkin-preview').src = result.preview; if (!quiet) toast('已生成打卡预览'); }
async function uploadCheckinFile(file) { if (!file?.type?.startsWith('image/')) { toast('请粘贴或选择真实图片文件。'); return; } const result = normalizeResponse(await upload('/upload-checkin-background', file)); if (!result.image) throw new Error('背景上传失败'); $('#checkin-template-form').elements.image.value = result.image; await updateCheckinPreview(true); toast('打卡背景已上传'); }

$('#refresh').addEventListener('click', () => safely(loadAll));
$$('.type-filter button').forEach((button) => button.addEventListener('click', () => { selectedFilter = button.dataset.filter; $$('.type-filter button').forEach((entry) => entry.classList.toggle('active', entry === button)); renderList(); }));
$('#character-form').elements.kind.addEventListener('change', (event) => toggleKindFields(event.target.value));
$('#new-character').addEventListener('click', () => { selectedId = ''; const form = $('#character-form'); form.reset(); form.elements.kind.value = 'companion'; form.elements.quality.value = 'SR'; form.elements.focal_x.value = '0.5'; form.elements.focal_y.value = '0.5'; toggleKindFields('companion'); $('#preview-image').removeAttribute('src'); $('#preview-title').textContent = '新增条目'; $('#preview-subtitle').textContent = '填写资料后上传图片；可调画面焦点。'; renderList(); });
$('#save-button').addEventListener('click', () => safely(async () => { const data = readForm(); if (!data.id || !data.name) { toast('ID 和中文名称必填'); return; } if (data.kind === 'skin' && !data.parent_id) { toast('皮肤必须选择所属同伴'); return; } $('#save-state').textContent = '保存中…'; const result = normalizeResponse(await apiPost('/characters', data)); $('#save-state').textContent = ''; selectedId = result.character?.id || data.id; toast('已保存条目'); await loadAll(); }));
$('#delete-button').addEventListener('click', () => safely(async () => { const id = $('#character-form').elements.id.value.trim(); if (!id || !confirmDelete($('#delete-button'), `条目 ${id}（玩家已有资产不会自动删除）`)) return; await apiDelete(`/characters/${id}`); selectedId = ''; toast('已删除条目'); await loadAll(); }));
bindImageDropzone('#image-dropzone', '#image-upload', uploadEntryFile, 'pasted-entry.png');

$('#save-settings').addEventListener('click', () => safely(async () => { const result = normalizeResponse(await apiPost('/settings', readSettings())); settings = result.settings || settings; toast('视觉色板已保存'); }));
$('#known-player').addEventListener('change', (event) => { const player = players[Number(event.target.value)]; if (!player) return; $('#grant-scope').value = player.scope_id; $('#grant-user').value = player.user_id; $('#grant-name').value = player.name; });
function grantPayload() { return { scope_id: $('#grant-scope').value.trim(), user_id: $('#grant-user').value.trim(), name: $('#grant-name').value.trim() }; }
$('#grant-button').addEventListener('click', () => safely(async () => { const payload = { ...grantPayload(), character_id: $('#grant-character').value }; if (!payload.scope_id || !payload.user_id || !payload.character_id) { toast('请填写群/用户/条目'); return; } const result = normalizeResponse(await apiPost('/grant', payload)); toast(result.created ? '已发放条目' : '玩家已拥有该条目'); await loadAll(); }));
$('#grant-exclusive-button').addEventListener('click', () => safely(async () => { const select = $('#grant-exclusive'); const option = select.options[select.selectedIndex]; const payload = { ...grantPayload(), companion_id: select.value, exclusive_name: option?.dataset.exclusiveName || '' }; if (!payload.scope_id || !payload.user_id || !payload.companion_id || !payload.exclusive_name) { toast('请填写群/用户并选择专属物品'); return; } await apiPost('/grant-exclusive', payload); toast('已发放专属物品'); await loadAll(); }));

$('#new-checkin-template').addEventListener('click', () => { selectedTemplateId = ''; fillTemplate(newTemplate()); renderTemplateList(); });
$('#checkin-template-form').addEventListener('input', scheduleCheckinPreview);
$('#preview-checkin-template').addEventListener('click', () => safely(() => updateCheckinPreview(false)));
$('#save-checkin-template').addEventListener('click', () => safely(async () => { const template = readTemplate(); if (!template.id || !template.name) { toast('模板 ID 和名称必填'); return; } const result = normalizeResponse(await apiPost('/checkin-templates', template)); selectedTemplateId = result.template?.id || template.id; toast('已保存打卡模板'); await loadAll(); }));
$('#delete-checkin-template').addEventListener('click', () => safely(async () => { const id = $('#checkin-template-form').elements.id.value.trim(); if (!id || !confirmDelete($('#delete-checkin-template'), `打卡模板 ${id}`)) return; await apiDelete(`/checkin-templates/${id}`); selectedTemplateId = ''; toast('已删除模板'); await loadAll(); }));
bindImageDropzone('#checkin-dropzone', '#checkin-background-upload', uploadCheckinFile, 'pasted-checkin.png');

async function boot() { if (bridge().ready) await bridge().ready(); await loadAll(); }
boot().catch((error) => { console.error(error); toast(errorText(error)); });
window.addEventListener('unhandledrejection', (event) => { console.error(event.reason); toast(errorText(event.reason)); });

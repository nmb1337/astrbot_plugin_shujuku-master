const PLUGIN = 'astrbot_plugin_juben_npc';
const $ = (selector) => document.querySelector(selector);

let characters = [];
let players = [];
let selectedId = '';
let checkinTemplates = [];
let selectedTemplateId = '';

const bridge = () => window.AstrBotPluginPage || {};

async function apiGet(path) {
  const api = bridge();
  const endpoint = path.replace(/^\//, '');
  if (api.apiGet) return api.apiGet(endpoint);
  if (api.request) return api.request({ method: 'GET', path: endpoint });
  return fetch(`/api/v1/plugins/extensions/${PLUGIN}${path}`).then((res) => res.json());
}

async function apiPost(path, data) {
  const api = bridge();
  const endpoint = path.replace(/^\//, '');
  if (api.apiPost) return api.apiPost(endpoint, data);
  if (api.request) return api.request({ method: 'POST', path: endpoint, data });
  return fetch(`/api/v1/plugins/extensions/${PLUGIN}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }).then((res) => res.json());
}

async function apiDelete(path) {
  const api = bridge();
  const endpoint = path.replace(/^\//, '');
  if (api.apiDelete) return api.apiDelete(endpoint);
  if (api.request) return api.request({ method: 'DELETE', path: endpoint });
  return fetch(`/api/v1/plugins/extensions/${PLUGIN}${path}`, { method: 'DELETE' }).then((res) => res.json());
}

async function upload(path, file) {
  const api = bridge();
  const endpoint = path.replace(/^\//, '');
  if (api.upload) return api.upload(endpoint, file);

  const form = new FormData();
  form.append('file', file);
  return fetch(`/api/v1/plugins/extensions/${PLUGIN}${path}`, { method: 'POST', body: form }).then((res) => res.json());
}

function assetUrl(image, kind = 'assets') {
  if (!image) return '';
  const api = bridge();
  if (api.getApiUrl) return api.getApiUrl(`${kind}/${encodeURIComponent(image)}`);
  return `/api/v1/plugins/extensions/${PLUGIN}/${kind}/${encodeURIComponent(image)}`;
}

function toast(message) {
  const el = $('#toast');
  el.textContent = message;
  el.classList.add('show');
  window.setTimeout(() => el.classList.remove('show'), 1800);
}

function normalizeResponse(result) {
  if (result && result.data) return result.data;
  return result || {};
}

async function loadAll() {
  const payload = normalizeResponse(await apiGet('/characters'));
  characters = payload.characters || [];
  players = payload.players || [];
  checkinTemplates = payload.checkin_templates || [];
  if (!selectedId && characters[0]) selectedId = characters[0].id;
  if (!selectedTemplateId && checkinTemplates[0]) selectedTemplateId = checkinTemplates[0].id;
  renderList();
  renderPlayerOptions();
  renderGrantCharacters();
  fillForm(characters.find((item) => item.id === selectedId) || characters[0]);
  renderTemplateList();
  fillTemplate(checkinTemplates.find((item) => item.id === selectedTemplateId) || checkinTemplates[0]);
}

function renderList() {
  const list = $('#character-list');
  list.innerHTML = '';
  characters.forEach((character) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `character-item ${character.id === selectedId ? 'active' : ''}`;
    item.innerHTML = `
      <img src="${assetUrl(character.image)}" alt="" />
      <span>
        <strong>${escapeHtml(character.name)}</strong>
        <span>${escapeHtml(character.skin || '默认')} · ${escapeHtml(character.star || 'R')}</span>
      </span>
    `;
    item.addEventListener('click', () => {
      selectedId = character.id;
      renderList();
      fillForm(character);
    });
    list.appendChild(item);
  });
}

function renderPlayerOptions() {
  const select = $('#known-player');
  select.innerHTML = '<option value="">手动填写</option>';
  players.forEach((player, index) => {
    const option = document.createElement('option');
    option.value = String(index);
    option.textContent = `${player.name} / ${player.user_id} / ${player.scope_id}`;
    select.appendChild(option);
  });
}

function renderGrantCharacters() {
  const select = $('#grant-character');
  select.innerHTML = '';
  characters.forEach((character) => {
    const option = document.createElement('option');
    option.value = character.id;
    option.textContent = `${character.name} / ${character.skin || '默认'}`;
    select.appendChild(option);
  });
}

function fillForm(character) {
  const form = $('#character-form');
  if (!character) {
    form.reset();
    return;
  }

  selectedId = character.id;
  form.elements.id.value = character.id || '';
  form.elements.name.value = character.name || '';
  form.elements.base.value = character.base || '';
  form.elements.skin.value = character.skin || '';
  form.elements.star.value = character.star || 'R';
  form.elements.route.value = character.route || '';
  form.elements.bonus.value = character.bonus || '';
  form.elements.intro.value = character.intro || '';
  form.elements.image.value = character.image || '';
  form.elements.featured.checked = Boolean(character.featured);
  const colors = character.colors || ['#6c8cff', '#f4d35e', '#10172a'];
  form.color0.value = colors[0] || '#6c8cff';
  form.color1.value = colors[1] || '#f4d35e';
  form.color2.value = colors[2] || '#10172a';
  const skills = character.skills || [];
  [0, 1, 2].forEach((index) => {
    form.elements[`skill${index}`].value = skills[index]?.[0] || '';
    form.elements[`skill${index}Desc`].value = skills[index]?.[1] || '';
  });

  $('#preview-image').src = assetUrl(character.image);
  $('#preview-title').textContent = character.name || '未命名角色';
  $('#preview-subtitle').textContent = `${character.skin || '默认'} · ${character.star || 'R'} · ${character.image || '未上传图片'}`;
}

function readForm() {
  const form = $('#character-form');
  return {
    id: form.elements.id.value.trim(),
    name: form.elements.name.value.trim(),
    base: form.elements.base.value.trim(),
    skin: form.elements.skin.value.trim(),
    star: form.elements.star.value,
    route: form.elements.route.value.trim(),
    bonus: form.elements.bonus.value.trim(),
    intro: form.elements.intro.value.trim(),
    image: form.elements.image.value.trim(),
    featured: form.elements.featured.checked,
    colors: [form.elements.color0.value, form.elements.color1.value, form.elements.color2.value],
    skills: [
      [form.elements.skill0.value.trim(), form.elements.skill0Desc.value.trim()],
      [form.elements.skill1.value.trim(), form.elements.skill1Desc.value.trim()],
      [form.elements.skill2.value.trim(), form.elements.skill2Desc.value.trim()],
    ],
  };
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

$('#refresh').addEventListener('click', loadAll);

$('#new-character').addEventListener('click', () => {
  selectedId = '';
  $('#character-form').reset();
  $('#character-form').elements.star.value = 'SR';
  $('#character-form').elements.color0.value = '#6c8cff';
  $('#character-form').elements.color1.value = '#f4d35e';
  $('#character-form').elements.color2.value = '#10172a';
  $('#preview-image').removeAttribute('src');
  $('#preview-title').textContent = '新增角色';
  $('#preview-subtitle').textContent = '填写信息并上传图片。';
  renderList();
});

$('#save-button').addEventListener('click', async () => {
  const data = readForm();
  if (!data.id || !data.name) {
    toast('ID 和名称必填');
    return;
  }
  $('#save-state').textContent = '保存中...';
  const result = normalizeResponse(await apiPost('/characters', data));
  $('#save-state').textContent = '';
  selectedId = result.character?.id || data.id;
  toast('已保存角色');
  await loadAll();
});

$('#delete-button').addEventListener('click', async () => {
  const id = $('#character-form').elements.id.value.trim();
  if (!id) return;
  if (!window.confirm(`确定删除 ${id}？玩家已有数据不会自动删除。`)) return;
  await apiDelete(`/characters/${encodeURIComponent(id)}`);
  selectedId = '';
  toast('已删除角色');
  await loadAll();
});

$('#upload-button').addEventListener('click', async () => {
  const file = $('#image-upload').files[0];
  if (!file) {
    toast('请选择图片');
    return;
  }
  const result = normalizeResponse(await upload('/upload-image', file));
  if (!result.image) {
    toast('上传失败');
    return;
  }
  $('#character-form').elements.image.value = result.image;
  $('#preview-image').src = assetUrl(result.image);
  toast('图片已上传');
});

$('#known-player').addEventListener('change', (event) => {
  const player = players[Number(event.target.value)];
  if (!player) return;
  $('#grant-scope').value = player.scope_id;
  $('#grant-user').value = player.user_id;
  $('#grant-name').value = player.name;
});

$('#grant-button').addEventListener('click', async () => {
  const payload = {
    scope_id: $('#grant-scope').value.trim(),
    user_id: $('#grant-user').value.trim(),
    name: $('#grant-name').value.trim(),
    character_id: $('#grant-character').value,
  };
  if (!payload.scope_id || !payload.user_id || !payload.character_id) {
    toast('请填写群/用户/角色');
    return;
  }
  const result = normalizeResponse(await apiPost('/grant', payload));
  toast(result.created ? '已赠送角色' : '玩家已拥有该角色');
  await loadAll();
});

function templateField(key, field) {
  return $(`#checkin-template-form [name="${key}-${field}"]`);
}

function newTemplate() {
  return {
    id: '', name: '', image: '', enabled: true,
    texts: {
      title: { text: '{title}', x: 0.07, y: 0.10, size: 0.075, color: '#ffffff', bold: true },
      reward: { text: '{reward}', x: 0.08, y: 0.30, size: 0.045, color: '#ffffff', bold: false },
      coins: { text: '当前星币：{coins}', x: 0.08, y: 0.40, size: 0.045, color: '#ffffff', bold: false },
      tickets: { text: '免费入场券：{tickets}', x: 0.08, y: 0.50, size: 0.045, color: '#ffffff', bold: false },
      probability: { text: '概率：1星币45% / 2星币30% / 3星币20% / 入场券5%', x: 0.08, y: 0.82, size: 0.030, color: '#ffffff', bold: false },
    },
  };
}

function renderTemplateList() {
  const list = $('#checkin-template-list');
  list.innerHTML = '';
  checkinTemplates.forEach((template) => {
    const item = document.createElement('button');
    item.type = 'button';
    item.className = `character-item ${template.id === selectedTemplateId ? 'active' : ''}`;
    item.innerHTML = `<img src="${assetUrl(template.image, 'checkin-assets')}" alt="" /><span><strong>${escapeHtml(template.name)}</strong><span>${template.enabled ? '已启用，打卡时随机抽取' : '已停用'}</span></span>`;
    item.addEventListener('click', () => {
      selectedTemplateId = template.id;
      renderTemplateList();
      fillTemplate(template);
    });
    list.appendChild(item);
  });
}

function fillTemplate(template) {
  const form = $('#checkin-template-form');
  if (!template) { form.reset(); return; }
  form.elements.id.value = template.id || '';
  form.elements.name.value = template.name || '';
  form.elements.image.value = template.image || '';
  form.elements.enabled.checked = Boolean(template.enabled);
  for (const key of ['title', 'reward', 'coins', 'tickets', 'probability']) {
    const text = template.texts?.[key] || {};
    templateField(key, 'text').value = text.text || '';
    templateField(key, 'x').value = text.x ?? 0;
    templateField(key, 'y').value = text.y ?? 0;
    templateField(key, 'size').value = text.size ?? 0.04;
    templateField(key, 'color').value = text.color || '#ffffff';
    templateField(key, 'bold').checked = Boolean(text.bold);
  }
  $('#checkin-preview').src = assetUrl(template.image, 'checkin-assets');
}

function readTemplate() {
  const form = $('#checkin-template-form');
  const template = { id: form.elements.id.value.trim(), name: form.elements.name.value.trim(), image: form.elements.image.value.trim(), enabled: form.elements.enabled.checked, texts: {} };
  for (const key of ['title', 'reward', 'coins', 'tickets', 'probability']) {
    template.texts[key] = {
      text: templateField(key, 'text').value.trim(),
      x: Number(templateField(key, 'x').value), y: Number(templateField(key, 'y').value),
      size: Number(templateField(key, 'size').value), color: templateField(key, 'color').value,
      bold: templateField(key, 'bold').checked,
    };
  }
  return template;
}

$('#new-checkin-template').addEventListener('click', () => {
  selectedTemplateId = '';
  fillTemplate(newTemplate());
  renderTemplateList();
});

$('#upload-checkin-background').addEventListener('click', async () => {
  const file = $('#checkin-background-upload').files[0];
  if (!file) { toast('请选择背景图片'); return; }
  const result = normalizeResponse(await upload('/upload-checkin-background', file));
  if (!result.image) { toast('背景上传失败'); return; }
  $('#checkin-template-form').elements.image.value = result.image;
  $('#checkin-preview').src = assetUrl(result.image, 'checkin-assets');
  toast('背景已上传；文字位置可在下方逐项调整');
});

$('#save-checkin-template').addEventListener('click', async () => {
  const template = readTemplate();
  if (!template.id || !template.name) { toast('模板 ID 和名称必填'); return; }
  const result = normalizeResponse(await apiPost('/checkin-templates', template));
  selectedTemplateId = result.template?.id || template.id;
  toast('已保存打卡模板');
  await loadAll();
});

$('#delete-checkin-template').addEventListener('click', async () => {
  const id = $('#checkin-template-form').elements.id.value.trim();
  if (!id || !window.confirm(`确定删除打卡模板 ${id}？`)) return;
  await apiDelete(`/checkin-templates/${encodeURIComponent(id)}`);
  selectedTemplateId = '';
  toast('已删除打卡模板');
  await loadAll();
});

async function boot() {
  if (bridge().ready) {
    await bridge().ready();
  }
  await loadAll();
}

boot().catch((error) => {
  console.error(error);
  toast('加载失败，请查看控制台');
});

const PLUGIN = 'astrbot_plugin_juben_npc';
const $ = (selector) => document.querySelector(selector);

let characters = [];
let players = [];
let selectedId = '';

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

function assetUrl(image) {
  if (!image) return '';
  const api = bridge();
  if (api.getApiUrl) return api.getApiUrl(`assets/${encodeURIComponent(image)}`);
  return `/api/v1/plugins/extensions/${PLUGIN}/assets/${encodeURIComponent(image)}`;
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
  if (!selectedId && characters[0]) selectedId = characters[0].id;
  renderList();
  renderPlayerOptions();
  renderGrantCharacters();
  fillForm(characters.find((item) => item.id === selectedId) || characters[0]);
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
  form.id.value = character.id || '';
  form.name.value = character.name || '';
  form.base.value = character.base || '';
  form.skin.value = character.skin || '';
  form.star.value = character.star || 'R';
  form.route.value = character.route || '';
  form.bonus.value = character.bonus || '';
  form.intro.value = character.intro || '';
  form.image.value = character.image || '';
  form.featured.checked = Boolean(character.featured);
  const colors = character.colors || ['#6c8cff', '#f4d35e', '#10172a'];
  form.color0.value = colors[0] || '#6c8cff';
  form.color1.value = colors[1] || '#f4d35e';
  form.color2.value = colors[2] || '#10172a';
  const skills = character.skills || [];
  [0, 1, 2].forEach((index) => {
    form[`skill${index}`].value = skills[index]?.[0] || '';
    form[`skill${index}Desc`].value = skills[index]?.[1] || '';
  });

  $('#preview-image').src = assetUrl(character.image);
  $('#preview-title').textContent = character.name || '未命名角色';
  $('#preview-subtitle').textContent = `${character.skin || '默认'} · ${character.star || 'R'} · ${character.image || '未上传图片'}`;
}

function readForm() {
  const form = $('#character-form');
  return {
    id: form.id.value.trim(),
    name: form.name.value.trim(),
    base: form.base.value.trim(),
    skin: form.skin.value.trim(),
    star: form.star.value,
    route: form.route.value.trim(),
    bonus: form.bonus.value.trim(),
    intro: form.intro.value.trim(),
    image: form.image.value.trim(),
    featured: form.featured.checked,
    colors: [form.color0.value, form.color1.value, form.color2.value],
    skills: [
      [form.skill0.value.trim(), form.skill0Desc.value.trim()],
      [form.skill1.value.trim(), form.skill1Desc.value.trim()],
      [form.skill2.value.trim(), form.skill2Desc.value.trim()],
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
  $('#character-form').star.value = 'SR';
  $('#character-form').color0.value = '#6c8cff';
  $('#character-form').color1.value = '#f4d35e';
  $('#character-form').color2.value = '#10172a';
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
  const id = $('#character-form').id.value.trim();
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
  $('#character-form').image.value = result.image;
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

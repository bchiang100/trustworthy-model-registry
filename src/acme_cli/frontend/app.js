// Main frontend application logic for ACME Registry.
// Frontend app for the registry UI
// This version calls the API routes under /api/v1 (see server in ../api)

const API_BASE = 'http://127.0.0.1:8000/api/v1';

function escapeHtml(s){ return String(s).replace(/[&<>\"]/g, c=>'&'+{'&':'amp','<':'lt','>':'gt','"':'quot'}[c]+';') }

// List models via POST /artifacts with a special wildcard query
async function fetchModels(){
  try{
    const body = [{ name: '*', types: ['model'] }];
    const res = await fetch(`${API_BASE}/artifacts`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
    if(!res.ok) throw new Error(`Failed to list models: ${res.status}`);
    return await res.json();
  }catch(err){
    console.error('fetchModels error', err);
    return [];
  }
}

async function renderList(containerId){
  const container = document.getElementById(containerId);
  if(!container) return;
  const list = await fetchModels();
  container.innerHTML = '';
  // If the API returned no models (or fetch failed), show a friendly message
  if(!list || list.length === 0){
    container.innerHTML = '<p class="muted">No models available or API unreachable.</p>';
    return;
  }
  // API returns objects with id and metadata
  list.slice().reverse().forEach(m=>{
    const name = m.metadata?.name || m.name || m.id;
    const desc = m.metadata?.description || m.desc || '';
    const license = (typeof m.metadata?.license === 'string' ? m.metadata.license : (m.license||'')).toString();
    const rating = m.metadata?.net_score ?? m.rating ?? 0;

    const el = document.createElement('div');
    el.className = 'card';
    el.innerHTML = `
      <div style="flex:1">
        <h3>${escapeHtml(name)}</h3>
        <p>${escapeHtml(desc)}</p>
        <p><small class="muted">license: ${escapeHtml(license)} • avg score: ${Number(rating).toFixed(2)}</small></p>
      </div>
      <div style="display:flex;flex-direction:column;gap:8px">
        <a class="ghost" href="model.html?id=${encodeURIComponent(m.id)}"><button>View</button></a>
      </div>
    `;
    container.appendChild(el);
  })
}

// Upload handler used by upload.html
// This will POST a file to /api/v1/models/upload and pass name/version via query params
async function uploadModel(form){
  const rawUrl = (form.url && form.url.value) ? form.url.value.trim() : '';
  const name = form.name.value.trim();
  const desc = form.desc.value.trim();
  const version = (form.version && form.version.value) ? form.version.value.trim() : '1.0.0';
  const fileInput = form.file || form.upload || null;
  const file = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;

  if(!name) return alert('Name required');
  if(!file) return alert('Please select a .zip file to upload');

  const fd = new FormData();
  fd.append('file', file, file.name);

  const q = `?name=${encodeURIComponent(name)}&version=${encodeURIComponent(version)}&description=${encodeURIComponent(desc)}`;
  try{
    const res = await fetch(`${API_BASE}/models/upload${q}`, { method: 'POST', body: fd });
    if(!res.ok){
      const text = await res.text();
      throw new Error(text || res.statusText);
    }
    const data = await res.json();
    alert(data.message || 'Upload started');
    // Redirect to model page if id returned
    if(data.model_id) window.location.href = 'model.html?id=' + encodeURIComponent(data.model_id);
  }catch(err){
    console.error('uploadModel error', err);
    alert('Upload failed: ' + (err.message||err));
  }
}


function deleteModel(id){
  // No delete endpoint in API v0.1; fallback to notifying user
  if(!confirm('Delete model (mock)? The API does not expose delete in this version.')) return;
  alert('Delete requested (local mock).');
  window.location.href='index.html';
}

// Ingest via the API - POST /artifact/model with JSON body {name, url}
async function doIngest(form){
  const url = form.url.value.trim();
  let name = (form.name && form.name.value && form.name.value.trim()) || '';
  const threshold = Number(form.threshold?.value || 0);
  if(!url) return alert('URL required');
  if(!name){
    // derive a simple name from the repo path
    try{ name = url.split('/').slice(-1)[0] || url; }catch(e){ name = url }
  }
  const payload = { name: name, url: url };
  const resultEl = document.getElementById('ingest-result');
  try{
    const res = await fetch(`${API_BASE}/artifact/model`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    if(!res.ok){
      const txt = await res.text(); throw new Error(txt||res.statusText);
    }
    const data = await res.json();
    const msg = `Ingest started (id: ${data?.metadata?.id || data?.data?.id || 'unknown'}).`;
    if(resultEl) resultEl.textContent = msg;
    else alert(msg);
  }catch(err){
    console.error('doIngest error', err);
    if(resultEl) resultEl.textContent = 'Ingest failed: ' + (err.message||err);
    else alert('Ingest failed: ' + (err.message||err));
  }
}

// Simple license compat check kept local
const compat = {
  'mit': ['mit','apache-2.0','bsd-3-clause'],
  'apache-2.0': ['apache-2.0','mit','bsd-3-clause'],
  'gpl-3.0': ['gpl-3.0'],
  'proprietary': []
};

function checkLicense(githubLicense, modelLicense){
  if(!githubLicense || !modelLicense) return false;
  const good = compat[githubLicense.toLowerCase()];
  if(!good) return false;
  return good.includes(modelLicense.toLowerCase());
}

function performLicenseCheck(form){
  const gh = form.github_license.value.trim().toLowerCase();
  const model = form.model_license.value.trim().toLowerCase();
  const ok = checkLicense(gh, model);
  alert(ok? 'Compatible — OK to use in project.':'Not compatible — do not use without legal review.');
}

// Regex search via POST /artifact/byRegEx
async function doRegexSearch(){
  const term = document.getElementById('q').value.trim();
  const container = document.getElementById('results');
  if(!container) return;
  if(!term) { container.innerHTML = '<p class="muted">Enter a regex</p>'; return; }
  try{
    const res = await fetch(`${API_BASE}/artifact/byRegEx`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ regex: term }) });
    if(res.status === 404){ container.innerHTML = '<p class="muted">No results</p>'; return; }
    if(!res.ok) throw new Error('Search failed');
    const list = await res.json();
    container.innerHTML = list.map(m=>`<div class="card"><div style="flex:1"><h3>${escapeHtml(m.name)}</h3><p><small class="muted">id: ${escapeHtml(String(m.id))} • type: ${escapeHtml(String(m.type))}</small></p></div><div><a href="model.html?id=${encodeURIComponent(m.id)}"><button>View</button></a></div></div>`).join('');
  }catch(e){ console.error('doRegexSearch', e); container.innerHTML = '<p class="muted">Search failed</p>'; }
}

// Search by artifact id via GET /artifacts/{type}/{id}
async function doIdSearch(){
  const type = document.getElementById('artifact-type').value;
  const id = document.getElementById('artifact-id').value.trim();
  const el = document.getElementById('id-result');
  if(!id) { if(el) el.innerHTML = '<p class="muted">Enter an id</p>'; return; }
  try{
    const res = await fetch(`${API_BASE}/artifacts/${encodeURIComponent(type)}/${encodeURIComponent(id)}`);
    if(res.status === 404){ if(el) el.innerHTML = '<p class="muted">Not found</p>'; return; }
    if(!res.ok) throw new Error('Lookup failed');
    const d = await res.json();
    if(el) el.innerHTML = `<div class="card"><h3>${escapeHtml(d.metadata.name)}</h3><p>Type: ${escapeHtml(d.metadata.type)}</p><p>URL: <a href="${escapeHtml(d.data.url)}">${escapeHtml(d.data.url)}</a></p></div>`;
  }catch(e){ console.error('doIdSearch', e); if(el) el.innerHTML = '<p class="muted">Lookup failed</p>'; }
}

// Reset registry via DELETE /reset
async function doReset(){
  if(!confirm('Reset registry? This will remove all in-memory metadata and may delete objects in S3.')) return;
  try{
    const res = await fetch(`${API_BASE}/reset`, { method: 'DELETE' });
    if(!res.ok) throw new Error('Reset failed');
    alert('Registry reset');
    renderList('model-list');
  }catch(e){ console.error('doReset', e); alert('Reset failed: ' + (e.message||e)); }
}

// On index load, render list from API
window.addEventListener('DOMContentLoaded',()=>{
  renderList('model-list');
});

// Export functions to global for inline onclick usage
window.uploadModel = uploadModel;
window.submitRating = submitRating;
window.deleteModel = deleteModel;
window.doIngest = doIngest;
window.performLicenseCheck = performLicenseCheck;
window.enumerateSearch = function(term, containerId){ enumerateSearch(term, containerId); };

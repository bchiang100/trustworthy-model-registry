// Frontend app for the registry UI
// This version calls the API routes under /api/v1 (see server in ../api)

const API_BASE = 'http://127.0.0.1:8000/api/v1';

function escapeHtml(s){ return String(s).replace(/[&<>\"]/g, c=>'&'+{'&':'amp','<':'lt','>':'gt','"':'quot'}[c]+';') }

async function fetchModels(search){
  try{
    let url = `${API_BASE}/models`;
    if(search) url += `?search=${encodeURIComponent(search)}`;
    const res = await fetch(url);
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

// Rating and delete are not implemented in API v0.1 - keep local fallbacks
function submitRating(id, value){
  // No rating endpoint in API v0.1; provide a client-side acknowledgement
  alert('Rating submitted (local mock) — API does not support ratings yet.');
}

function deleteModel(id){
  // No delete endpoint in API v0.1; fallback to notifying user
  if(!confirm('Delete model (mock)? The API does not expose delete in this version.')) return;
  alert('Delete requested (local mock).');
  window.location.href='index.html';
}

// Ingest via the API - sends a POST with huggingface_url query param
async function doIngest(form){
  const url = form.url.value.trim();
  const threshold = Number(form.threshold?.value || 0);
  if(!url) return alert('url required');
  try{
    const res = await fetch(`${API_BASE}/models/ingest?huggingface_url=${encodeURIComponent(url)}`, { method: 'POST' });
    if(!res.ok){
      const txt = await res.text(); throw new Error(txt||res.statusText);
    }
    const data = await res.json();
    const msg = `Ingest started. Estimated name: ${data.estimated_model_name || 'unknown'}. Status: ${data.status}`;
    alert(msg);
    // In real flow, backend would process and then the model would appear in listing
  }catch(err){
    console.error('doIngest error', err);
    alert('Ingest failed: ' + (err.message||err));
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

// Enumerate / regex search via API 'search' query
async function enumerateSearch(term, containerId){
  const container = document.getElementById(containerId);
  if(!container) return;
  try{
    const list = await fetchModels(term);
    if(!list || list.length===0) container.innerHTML = '<p class="muted">No results</p>';
    else container.innerHTML = list.map(m=>{
      const name = m.metadata?.name || m.name || m.id;
      const desc = m.metadata?.description || m.desc || '';
      const license = (typeof m.metadata?.license === 'string' ? m.metadata.license : (m.license||'')).toString();
      const rating = m.metadata?.net_score ?? m.rating ?? 0;
      return `<div class="card"><div style="flex:1"><h3>${escapeHtml(name)}</h3><p>${escapeHtml(desc)}</p><p><small class="muted">license:${escapeHtml(license)} • score:${Number(rating).toFixed(2)}</small></p></div><div><a href="model.html?id=${encodeURIComponent(m.id)}"><button>View</button></a></div></div>`
    }).join('');
  }catch(e){
    container.innerHTML = '<p class="muted">Search failed</p>';
  }
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

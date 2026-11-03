'use strict';
const $ = (id) => document.getElementById(id);
const state = {token: '', studies: [], study: null, frame: null, dirty: false, busy: false,
  saving: false, switching: false, modelBusy: false, models: [], playing: false, timer: null, files: [], thumbsStart: -1, thumbsData: [], sourceCoverage: null,
  intervals: [], intervalStart: null, savedFrameCount: 0, savedPositions: []};
let toastTimer;

function syncControls() {
  const running = state.busy || state.switching || state.saving || state.modelBusy;
  const blocked = running || !state.frame;
  for (const id of ['importBtn','emptyImportBtn','demoBtn']) $(id).disabled = running;
  for (const button of document.querySelectorAll('.study-button')) button.disabled = running;
  for (const id of ['bookmark','reviewLabel','reviewNote','jumpInput','scrubber','playBtn','zoomBtn','predictionImportBtn']) $(id).disabled = blocked;
  $('runModelBtn').disabled = blocked || !$('localModel').value;
  $('localModel').disabled = blocked;
  $('saveBtn').disabled = blocked || !state.dirty;
  $('prevBtn').disabled = blocked || state.frame.position === 0;
  $('nextBtn').disabled = blocked || state.frame.position >= state.study.frame_count - 1;
  $('intervalStartBtn').disabled = blocked || state.intervalStart !== null;
  $('intervalEndBtn').disabled = blocked || state.intervalStart === null
    || state.frame.position <= state.intervalStart;
  $('intervalCancelBtn').disabled = running || state.intervalStart === null;
  $('intervalNote').disabled = running || state.intervalStart === null;
}

function announce(message) { $('toast').textContent = message; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => {$('toast').hidden = true;}, 4000); }
function fail(error) { $('notice').textContent = error.message || String(error); $('notice').hidden = false; }
function clearError() { $('notice').hidden = true; }
function textElement(tag, text, className) { const el = document.createElement(tag);
  el.textContent = text; if (className) el.className = className; return el; }
async function api(path, options = {}) {
  const headers = {'X-Review-Token': state.token, ...options.headers};
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json';
  const response = await fetch(path, {...options, headers});
  if (!response.ok) { const data = await response.json().catch(() => ({}));
    throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${response.status}).`); }
  return response.json();
}
function base() { return `/api/studies/${state.study.id}`; }
function imageURL(position, thumb = false) {
  return `${base()}/frames/${position}/image${thumb ? '?thumbnail=true' : ''}`;
}
async function refreshLibrary() {
  state.studies = await api('/api/studies'); $('studyCount').textContent = state.studies.length;
  $('studies').replaceChildren();
  if (!state.studies.length) $('studies').append(textElement('p', 'No examinations imported.', 'muted'));
  for (const study of state.studies) {
    const button = textElement('button', '', `study-button${state.study?.id === study.id ? ' active' : ''}`);
    button.disabled = state.busy || state.switching || state.saving;
    button.append(textElement('strong', study.title), textElement('span', `${study.frame_count.toLocaleString()} frames · ${study.saved_count} saved`));
    if (study.synthetic) button.append(textElement('span', 'SYNTHETIC TEST DATA', 'test-tag'));
    button.addEventListener('click', () => selectStudy(study.id).catch(fail)); $('studies').append(button);
  }
}
function stopPlayback() { state.playing = false; clearTimeout(state.timer);
  $('playBtn').textContent = 'Play'; $('playBtn').setAttribute('aria-label', 'Play frames'); }
function renderSourceContinuity() {
  const data = state.sourceCoverage;
  const frameCount = data.imported_frames.toLocaleString();
  const common = data.common_forward_index_step;
  let message;
  if (data.assessment === 'index-jumps' && common !== null) {
    const pairCount = data.observed_forward_index_steps.toLocaleString();
    if (data.regular_observed_source_stride) {
      message = `Source-index audit: ${frameCount} imported images have a consistent observed +${common.toLocaleString()} index stride across ${pairCount} adjacent pairs. This is sparse imported coverage, not verified consecutive footage.`;
    } else {
      message = `Source-index audit: ${frameCount} imported images, common index step +${common.toLocaleString()} in ${data.common_step_pairs.toLocaleString()}/${pairCount} adjacent pairs, with ${data.unusual_forward_index_steps.toLocaleString()} differently spaced ${data.unusual_forward_index_steps === 1 ? 'pair' : 'pairs'} (largest forward step +${data.maximum_forward_index_step.toLocaleString()}). Imported footage may have additional gaps.`;
    }
  } else if (data.assessment === 'index-jumps') {
    message = `Source-index audit: ${frameCount} imported images, ${data.adjacent_index_jumps.toLocaleString()} jumps greater than +1 (largest +${data.maximum_forward_index_step.toLocaleString()}); no consistent source-index stride established. Not verified consecutive footage.`;
  } else if (data.assessment === 'consecutive-imported-indices') {
    message = `Source-index audit: all ${frameCount} imported source IDs are adjacent (+1). This does not establish complete capture or elapsed time.`;
  } else if (data.assessment === 'nonmonotonic') {
    message = 'Source-index audit: imported source IDs are repeated or not strictly increasing. Source-order continuity is not verified.';
  } else {
    message = `Source-index audit: continuity cannot be established (${data.unnumbered_frames.toLocaleString()} unnumbered images or insufficient source positions).`;
  }
  $('sourceContinuity').textContent = message + ' Preview speed is not acquisition timing.';
}
function renderSourceStep(position) {
  const previous = state.thumbsData.find(item => item.position === position - 1);
  const current = state.frame;
  const stepEl = $('sourceStep');
  if (!previous || previous.source_index === null || current.source_index === null) {
    stepEl.hidden = true;
    stepEl.textContent = '';
    return;
  }
  const step = current.source_index - previous.source_index;
  const common = state.sourceCoverage.common_forward_index_step;
  let message = '';
  if (step <= 0) {
    message = `Imported source IDs are repeated or decreasing (#${previous.source_index} to #${current.source_index}). Source order requires verification.`;
  } else if (common !== null && step !== common) {
    message = `Unusual source-index step: #${previous.source_index} to #${current.source_index} (+${step.toLocaleString()}), versus the common observed step +${common.toLocaleString()}. Intermediate source positions, when any, are not represented in this import.`;
  } else if (common === null && step > 1) {
    message = `Imported source IDs jump from #${previous.source_index} to #${current.source_index} (+${step.toLocaleString()} index steps). Intermediate index positions are not represented in this import.`;
  }
  stepEl.textContent = message;
  stepEl.hidden = !message;
}
async function selectStudy(id) {
  if (state.busy || state.switching || state.saving || state.modelBusy) return;
  state.switching = true; syncControls();
  try {
  stopPlayback(); if (state.dirty && !(await saveReview())) return;
  clearError(); state.study = await api(`/api/studies/${id}`); state.frame = null; state.thumbsStart = -1;
  state.intervalStart = null; state.intervals = []; state.savedFrameCount = 0; state.savedPositions = [];
  $('intervalNote').value = ''; renderIntervalDraft();
  state.thumbsData = []; state.sourceCoverage = await api(`${base()}/source-coverage`);
  renderSourceContinuity();
  $('emptyState').hidden = true; $('examination').hidden = false;
  $('studyTitle').textContent = state.study.title; $('sourceText').textContent = state.study.source;
  $('syntheticBanner').hidden = !state.study.synthetic;
  $('scrubber').max = state.study.frame_count - 1; $('jumpInput').max = state.study.frame_count;
  $('predictionImportBtn').disabled = false; $('referencePanel').open = false;
  for (const id of ['bookmark', 'reviewLabel', 'reviewNote']) $(id).disabled = false;
  await navigate(state.study.last_position, true); await refreshLibrary(); await loadSaved(); await loadIntervals(); await refreshModels();
  } finally { state.switching = false; syncControls(); }
}
function markDirty() { if (!state.frame) return; state.dirty = true;
  $('saveStatus').textContent = 'Unsaved'; $('saveBtn').disabled = false; }
async function saveReview() {
  if (!state.frame || !state.dirty) return true;
  if (state.saving) return false;
  state.saving = true; $('saveStatus').textContent = 'Saving…'; $('saveBtn').disabled = true;
  const inputIds = ['bookmark', 'reviewLabel', 'reviewNote']; inputIds.forEach(id => $(id).disabled = true);
  try {
    const review = await api(`${base()}/frames/${state.frame.position}/review`, {
      method: 'PUT', body: JSON.stringify({revision: state.frame.review.revision,
        bookmarked: $('bookmark').checked, note: $('reviewNote').value, label: $('reviewLabel').value})});
    state.frame.review = review; state.dirty = false; $('saveStatus').textContent = 'Saved';
    await loadSaved(); await refreshLibrary(); return true;
  } catch (e) { fail(e); $('saveStatus').textContent = 'Not saved'; $('saveBtn').disabled = false;
    stopPlayback(); return false;
  } finally { state.saving = false; syncControls(); }
}
async function navigate(position, force = false) {
  if (!state.study || state.busy || state.modelBusy || (state.switching && !force)) return false;
  position = Math.max(0, Math.min(state.study.frame_count - 1, Number(position)));
  if (!Number.isFinite(position) || !Number.isInteger(position)) return false;
  if (state.frame?.position === position && !force) return true;
  state.busy = true; syncControls();
  try {
    if (state.dirty && !(await saveReview())) return false;
    const frame = await api(`${base()}/frames/${position}`); state.frame = frame;
    $('imageLoading').hidden = false; $('frameImage').src = imageURL(position);
    $('frameImage').alt = state.study.synthetic ? `Synthetic software-test frame ${position + 1}; not clinical data` : `Examination frame ${position + 1}`;
    $('frameCounter').textContent = `Frame ${(position + 1).toLocaleString()} / ${state.study.frame_count.toLocaleString()}`;
    $('sourceIndex').textContent = frame.source_index !== null ? `Source #${frame.source_index}` : 'No acquisition time supplied';
    $('frameFilename').textContent = `${frame.filename} · original SHA-256 ${frame.source_sha256.slice(0, 12)}…`;
    $('jumpInput').value = position + 1; $('scrubber').value = position;
    $('prevBtn').disabled = position === 0; $('nextBtn').disabled = position === state.study.frame_count - 1;
    $('bookmark').checked = frame.review.bookmarked; $('reviewLabel').value = frame.review.label;
    $('reviewNote').value = frame.review.note; $('saveStatus').textContent = frame.review.revision ? 'Saved' : 'No notes';
    $('saveBtn').disabled = true; state.dirty = false; renderReference(); renderPredictions();
    await renderFilmstrip(position); renderSourceStep(position); renderIntervalDraft();
    await api(`${base()}/position`, {method: 'PUT', body: JSON.stringify({position})});
    return true;
  } catch (e) { fail(e); stopPlayback(); return false; }
  finally { state.busy = false; syncControls(); }
}
$('frameImage').addEventListener('load', () => {$('imageLoading').hidden = true;});
$('frameImage').addEventListener('error', () => {$('imageLoading').hidden = true; fail(new Error('This frame could not be loaded.'))});
async function renderFilmstrip(position) {
  const start = Math.max(0, Math.min(position - 5, state.study.frame_count - 12));
  if (start !== state.thumbsStart) {
    const frames = await api(`${base()}/frames?offset=${start}&limit=12`);
    $('filmstrip').replaceChildren(); state.thumbsStart = start; state.thumbsData = frames;
    for (const f of frames) {
      const button = textElement('button', '', 'thumb'); button.dataset.position = f.position;
      button.setAttribute('aria-label', `Open frame ${f.position + 1}`);
      const img = document.createElement('img'); img.src = imageURL(f.position, true); img.alt = ''; img.loading = 'lazy';
      button.append(img, textElement('span', String(f.position + 1)));
      button.addEventListener('click', () => {stopPlayback(); navigate(f.position);}); $('filmstrip').append(button);
    }
  }
  for (const button of $('filmstrip').children) { const active = Number(button.dataset.position) === position;
    button.classList.toggle('active', active); button.setAttribute('aria-pressed', active); }
}
function renderReference() {
  $('referenceLabels').replaceChildren();
  const entries = Object.entries(state.frame.reference_labels);
  if (!entries.length) {$('referenceLabels').append(textElement('p', 'No reference annotations were imported.', 'muted')); return;}
  for (const [key, value] of entries) { const row = textElement('div', '', 'reference-row');
    row.append(textElement('span', key), textElement('span', value === null ? 'Not supplied' : String(value)));
    $('referenceLabels').append(row); }
}
function renderPredictions() {
  $('predictions').replaceChildren(); const rows = state.frame.predictions;
  if (!rows.length) {$('predictions').append(textElement('p', state.study.runs.length ? 'No imported predictions for this frame.' : 'No model connected. No predictions are being generated.', 'muted')); return;}
  for (const prediction of rows) {
    const row = textElement('div', '', 'prediction');
    row.append(textElement('strong', `${prediction.label} · score ${prediction.score.toFixed(3)}`),
      textElement('small', prediction.model.name));
    const details = document.createElement('details');
    details.append(textElement('summary', 'Model details'),
      textElement('small', `${prediction.model.version} · ${prediction.model.run_id}`));
    if (prediction.model.description) details.append(textElement('small', prediction.model.description));
    row.append(details);
    const copy = textElement('button', 'Use as reviewer label', 'quiet compact');
    copy.addEventListener('click', () => {$('reviewLabel').value = prediction.label; markDirty();}); row.append(copy); $('predictions').append(row);
  }
  $('predictions').append(textElement('p', 'Model scores are not diagnostic certainty. Suggestions do not change your notes.', 'panel-hint'));
}
function renderExportEvidence() {
  if (!state.study) return;
  const selected = new Set(state.savedPositions);
  const interior = new Set();
  for (const interval of state.intervals) {
    selected.add(interval.start_position);
    selected.add(interval.end_position);
    for (let i = interval.start_position + 1; i < interval.end_position; i++) interior.add(i);
  }
  const omitted = [...interior].filter(position => !selected.has(position)).length;
  if (!selected.size) {
    $('exportEvidenceSummary').textContent = 'Nothing selected for export. Save a frame or mark an image interval.';
    return;
  }
  let message = `Saved export selection: ${selected.size.toLocaleString()} of ${state.study.frame_count.toLocaleString()} imported images.`;
  if (state.intervals.length) {
    const noun = omitted === 1 ? 'image is' : 'images are';
    message += ` ${omitted.toLocaleString()} marked-interval interior ${noun} not selected for export; only boundaries and separately saved images are included.`;
  }
  message += ' Selected images are not proof of viewing or medical findings.';
  if (selected.size > 250) message += ' This selection exceeds the 250-image export limit.';
  $('exportEvidenceSummary').textContent = message;
}
async function loadSaved() {
  const saved = await api(`${base()}/saved`); state.savedFrameCount = saved.length;
  state.savedPositions = saved.map(item => item.position);
  renderExportEvidence();
  $('savedCount').textContent = saved.length;
  $('exportBtn').disabled = saved.length === 0 && state.intervals.length === 0;
  $('savedFrames').replaceChildren();
  if (!saved.length) {$('savedFrames').append(textElement('p', 'Bookmarks and notes will appear here.', 'muted')); return;}
  for (const item of saved) {
    const button = textElement('button', '', 'saved-button');
    const img = document.createElement('img'); img.src = imageURL(item.position, true); img.alt = ''; img.loading = 'lazy';
    const copy = document.createElement('span'); copy.append(textElement('strong', `Frame ${item.position + 1}${item.label ? ' · ' + item.label : ''}`),textElement('small', item.note || 'Bookmark'));
    button.append(img, copy); button.addEventListener('click', () => {stopPlayback(); navigate(item.position);}); $('savedFrames').append(button);
  }
}
function renderIntervalDraft() {
  if (state.intervalStart === null) {
    $('intervalDraft').textContent = 'No interval in progress.';
  } else {
    const start = state.intervalStart + 1;
    $('intervalDraft').textContent = `Start marked at imported frame ${start}. Navigate to a later image and select Save end. The interval is not saved until then.`;
  }
  syncControls();
}
async function loadIntervals() {
  state.intervals = await api(`${base()}/intervals`);
  $('intervalCount').textContent = state.intervals.length;
  renderExportEvidence();
  $('exportBtn').disabled = state.savedFrameCount === 0 && state.intervals.length === 0;
  $('intervals').replaceChildren();
  if (!state.intervals.length) {
    $('intervals').append(textElement('p', 'No image intervals marked.', 'muted'));
    return;
  }
  for (const interval of state.intervals) {
    const entry = document.createElement('div'); entry.className = 'interval-entry';
    const start = interval.start_position + 1, end = interval.end_position + 1;
    entry.append(textElement('strong', `Imported frames ${start}–${end}`));
    const source = interval.start_source_index !== null && interval.end_source_index !== null
      ? ` · observed source IDs #${interval.start_source_index}–#${interval.end_source_index}` : '';
    entry.append(textElement('small', `${end - start + 1} imported positions in selection${source} · no timing inferred`));
    if (interval.note) entry.append(textElement('p', interval.note));
    const actions = document.createElement('div'); actions.className = 'interval-entry-actions';
    for (const [title, position] of [['Go to start', interval.start_position], ['Go to end', interval.end_position]]) {
      const button = textElement('button', title, 'quiet compact');
      button.addEventListener('click', () => {stopPlayback(); navigate(position).catch(fail);});
      actions.append(button);
    }
    const remove = textElement('button', 'Remove interval', 'quiet compact');
    remove.setAttribute('aria-label', `Remove interval ${start} to ${end}`);
    remove.addEventListener('click', async () => {
      if (!window.confirm(`Remove marked image interval ${start}–${end}? The deletion is recorded in export history.`)) return;
      try {
        await api(`${base()}/intervals/${interval.id}`, {method:'DELETE'});
        await loadIntervals();
        announce('Interval removed.');
      } catch (error) {fail(error);}
    });
    actions.append(remove); entry.append(actions); $('intervals').append(entry);
  }
}
$('intervalStartBtn').addEventListener('click', () => {
  if (!state.frame || state.intervalStart !== null) return;
  stopPlayback(); state.intervalStart = state.frame.position;
  renderIntervalDraft(); announce('Start image marked. Navigate forward to save an interval.');
});
$('intervalCancelBtn').addEventListener('click', () => {
  state.intervalStart = null; $('intervalNote').value = '';
  renderIntervalDraft(); announce('Unsaved interval cancelled.');
});
$('intervalEndBtn').addEventListener('click', async () => {
  if (!state.frame || state.intervalStart === null || state.frame.position <= state.intervalStart) return;
  try {
    await api(`${base()}/intervals`, {method:'POST', body:JSON.stringify({
      start_position:state.intervalStart, end_position:state.frame.position,
      note:$('intervalNote').value
    })});
    state.intervalStart = null; $('intervalNote').value = '';
    renderIntervalDraft(); await loadIntervals();
    announce('Reviewer-marked image interval saved locally.');
  } catch (error) {fail(error);}
});
async function playbackTick() {
  if (!state.playing || !state.frame) return;
  if (state.frame.position >= state.study.frame_count - 1) {stopPlayback(); return;}
  const ok = await navigate(state.frame.position + 1);
  if (!ok) {stopPlayback(); return;}
  if (state.playing) state.timer = setTimeout(playbackTick, 1000 / Number($('speed').value));
}
$('playBtn').addEventListener('click', () => { if (state.playing) {stopPlayback(); return;}
  state.playing = true; $('playBtn').textContent = 'Pause'; $('playBtn').setAttribute('aria-label', 'Pause frames'); playbackTick(); });
$('prevBtn').addEventListener('click', () => {stopPlayback(); navigate(state.frame.position - 1);});
$('nextBtn').addEventListener('click', () => {stopPlayback(); navigate(state.frame.position + 1);});
$('scrubber').addEventListener('change', () => {stopPlayback(); navigate($('scrubber').value);});
$('jumpInput').addEventListener('change', () => {stopPlayback(); navigate(Number($('jumpInput').value) - 1);});
$('zoomBtn').addEventListener('click', () => {const on = $('imageStage').classList.toggle('zoomed'); $('zoomBtn').setAttribute('aria-pressed', on);});
$('saveBtn').addEventListener('click', () => saveReview());
$('bookmark').addEventListener('change', async () => {stopPlayback(); markDirty(); await saveReview();});
for (const id of ['reviewLabel','reviewNote']) $(id).addEventListener('input', () => {stopPlayback(); markDirty();});
window.addEventListener('beforeunload', (event) => {if (state.dirty) {event.preventDefault(); event.returnValue = '';}});
document.addEventListener('keydown', (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {event.preventDefault(); saveReview(); return;}
  if (document.querySelector('dialog[open]') || ['INPUT','TEXTAREA','SELECT'].includes(event.target.tagName) || !state.frame) return;
  if (event.key === 'ArrowLeft') {event.preventDefault(); $('prevBtn').click();}
  if (event.key === 'ArrowRight') {event.preventDefault(); $('nextBtn').click();}
  if (event.key.toLowerCase() === 'b') {event.preventDefault(); $('bookmark').click();}
  if (event.code === 'Space') {event.preventDefault(); $('playBtn').click();}
});
function openImport() {stopPlayback(); $('importDialog').showModal();}
$('importBtn').addEventListener('click', openImport); $('emptyImportBtn').addEventListener('click', openImport);
$('helpBtn').addEventListener('click', () => {$('helpDialog').showModal();});
for (const button of document.querySelectorAll('[data-close]')) button.addEventListener('click', () => $(button.dataset.close).close());
$('chooseFilesBtn').addEventListener('click', () => $('fileInput').click());
$('chooseFolderBtn').addEventListener('click', () => $('folderInput').click());
function selectFiles(input) {
  state.files = [...input.files].filter(f => /\.(png|jpe?g|webp)$/i.test(f.name));
  const size = state.files.reduce((sum, f) => sum + f.size, 0); const skipped = input.files.length - state.files.length;
  $('fileSelection').textContent = `${state.files.length} images · ${(size / 1024 / 1024).toFixed(1)} MiB${skipped ? ` · ${skipped} unsupported files omitted` : ''}`;
  if (!$('importTitle').value && state.files[0]) $('importTitle').value = state.files[0].webkitRelativePath?.split('/')[0] || 'Image sequence';
  $('submitImport').disabled = !state.files.length || state.files.length > 1000 || size > 512 * 1024 * 1024;
  $('importError').textContent = state.files.length > 1000 || size > 512 * 1024 * 1024 ? 'Use the CLI importer for more than 1,000 frames or 512 MiB.' : '';
}
for (const id of ['fileInput','folderInput']) $(id).addEventListener('change', () => selectFiles($(id)));
$('importForm').addEventListener('submit', async (event) => {
  event.preventDefault(); if (!state.files.length) return;
  $('submitImport').disabled = true; $('submitImport').textContent = 'Importing…'; $('importError').textContent = '';
  const form = new FormData(); form.append('title', $('importTitle').value); form.append('source', $('importSource').value || 'Local research images');
  for (const file of state.files) form.append('files', file, file.name);
  try { const study = await api('/api/studies/import', {method:'POST', body:form});
    $('importDialog').close(); state.files = []; $('importForm').reset(); $('fileSelection').textContent = 'No images selected.';
    await refreshLibrary(); await selectStudy(study.id); announce('Examination imported locally.');
  } catch (e) {$('importError').textContent = e.message;}
  finally {$('submitImport').textContent = 'Import locally'; $('submitImport').disabled = !state.files.length;}
});
$('demoBtn').addEventListener('click', async () => {
  stopPlayback(); $('demoBtn').disabled = true;
  try {const existing = state.studies.find(s => s.synthetic); const study = existing || await api('/api/demo', {method:'POST'});
    await selectStudy(study.id); announce('Synthetic test sequence. No clinical data or model predictions.');
  } catch (e) {fail(e);} finally {$('demoBtn').disabled = false;}
});
$('exportBtn').addEventListener('click', async () => {
  stopPlayback(); if (!(await saveReview())) return;
  try { const response = await fetch(`${base()}/export`);
    if (!response.ok) {const data = await response.json(); throw new Error(data.detail);}
    const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement('a');
    link.href = url; link.download = `review-${state.study.id.slice(0,8)}.zip`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 5000); announce('Review exported. Open review.html inside the ZIP.');
  } catch (e) {fail(e);}
});
$('predictionImportBtn').addEventListener('click', () => $('predictionFile').click());
$('predictionFile').addEventListener('change', async () => {
  const file = $('predictionFile').files[0]; if (!file) return; stopPlayback();
  try {if (file.size > 20 * 1024 * 1024) throw new Error('Prediction JSON must be at most 20 MiB.');
    if (!(await saveReview())) return;
    const payload = JSON.parse(await file.text()); await api(`${base()}/predictions`, {method:'POST', body:JSON.stringify(payload)});
    state.study = await api(base()); await navigate(state.frame.position, true); announce('Model output imported; reviewer notes are unchanged.');
  } catch (e) {fail(e);} finally {$('predictionFile').value = '';}
});

async function refreshModels() {
  state.models = await api('/api/models');
  const compatible = state.models.filter(model => model.synthetic_test === Boolean(state.study?.synthetic));
  $('localModel').replaceChildren();
  for (const model of compatible) {
    const option = textElement('option', model.name); option.value = model.id; $('localModel').append(option);
  }
  $('localModelControls').hidden = compatible.length === 0;
  syncControls();
}
$('localModel').addEventListener('change', syncControls);
$('runModelBtn').addEventListener('click', async () => {
  if (!state.study || state.modelBusy || !$('localModel').value) return;
  stopPlayback(); if (!(await saveReview())) return;
  const studyId = state.study.id;
  state.modelBusy = true; syncControls(); $('runModelBtn').textContent = 'Running locally…';
  let completed = false;
  try {
    await api(`/api/studies/${studyId}/predict`, {method:'POST', body:JSON.stringify({model_id: $('localModel').value})});
    completed = true;
  } catch (error) {fail(error);}
  finally {state.modelBusy = false; $('runModelBtn').textContent = 'Run local model'; syncControls();}
  if (completed && state.study?.id === studyId) {
    try {state.study = await api(base()); await navigate(state.frame.position, true); announce('Local model finished. Reviewer notes are unchanged.');}
    catch (error) {fail(error);}
  }
});

(async () => {
  try {const config = await api('/api/config'); state.token = config.token; $('version').textContent = `v${config.version}`;
    await refreshLibrary(); if (state.studies.length) await selectStudy(state.studies[0].id);
  } catch (e) {fail(e);}
})();

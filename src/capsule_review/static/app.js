'use strict';
const $ = (id) => document.getElementById(id);
const state = {token: '', studies: [], study: null, frame: null, dirty: false, busy: false,
  saving: false, switching: false, modelBusy: false, auditBusy: false, models: [], playing: false, timer: null, files: [], thumbsStart: -1, thumbsData: [], sourceCoverage: null,
  intervals: [], intervalStart: null, savedFrameCount: 0, savedPositions: [],
  prioritySources: [], priorityQuery: null, priorityData: null, priorityBusy: false};
let toastTimer;

function syncControls() {
  const running = state.busy || state.switching || state.saving || state.modelBusy || state.auditBusy;
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
  $('auditBtn').disabled = running || !state.study || (state.savedFrameCount === 0 && state.intervals.length === 0);
  $('fullSpanBtn').disabled = running || !state.study || state.intervals.length === 0;
  const priorityBlocked = running || state.priorityBusy || !state.prioritySources.length;
  for (const id of ['prioritySource', 'priorityCount', 'priorityMethod', 'priorityBuild']) $(id).disabled = priorityBlocked;
  $('priorityPrev').disabled = priorityBlocked || !state.priorityData || state.priorityData.offset === 0;
  $('priorityNext').disabled = priorityBlocked || !state.priorityData ||
    state.priorityData.offset + state.priorityData.items.length >= state.priorityData.selected_images;
}

function announce(message) { $('toast').textContent = message; $('toast').hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => {$('toast').hidden = true;}, 4000); }
function fail(error) { $('notice').textContent = error.message || String(error); $('notice').hidden = false; }
function clearError() { $('notice').hidden = true; }
function clearEvidenceAudit() { $('auditReport').textContent = ''; $('auditReport').hidden = true; }
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
  if (state.busy || state.switching || state.saving || state.modelBusy || state.auditBusy) return;
  state.switching = true; syncControls();
  try {
  stopPlayback(); if (state.dirty && !(await saveReview())) return;
  clearError(); clearEvidenceAudit(); state.study = await api(`/api/studies/${id}`); state.frame = null; state.thumbsStart = -1;
  state.intervalStart = null; state.intervals = []; state.savedFrameCount = 0; state.savedPositions = [];
  state.prioritySources = []; state.priorityQuery = null; state.priorityData = null; resetPriorityDisplay();
  $('intervalNote').value = ''; renderIntervalDraft();
  state.thumbsData = []; state.sourceCoverage = await api(`${base()}/source-coverage`);
  renderSourceContinuity();
  $('emptyState').hidden = true; $('examination').hidden = false;
  $('studyTitle').textContent = state.study.title; $('sourceText').textContent = state.study.source;
  $('syntheticBanner').hidden = !state.study.synthetic;
  $('scrubber').max = state.study.frame_count - 1; $('jumpInput').max = state.study.frame_count;
  $('predictionImportBtn').disabled = false; $('referencePanel').open = false;
  for (const id of ['bookmark', 'reviewLabel', 'reviewNote']) $(id).disabled = false;
  await navigate(state.study.last_position, true); await refreshLibrary(); await loadSaved(); await loadIntervals(); await refreshModels(); await loadPriorityRuns();
  } finally { state.switching = false; syncControls(); }
}
function markDirty() { if (!state.frame) return; clearEvidenceAudit(); state.dirty = true;
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
    state.frame.review = review; state.dirty = false; clearEvidenceAudit(); $('saveStatus').textContent = 'Saved';
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
    const fullSpanSelection = new Set(selected);
    for (const interval of state.intervals) {
      for (let position = interval.start_position; position <= interval.end_position; position++) fullSpanSelection.add(position);
    }
    message += ` The optional full-span archive would retain ${fullSpanSelection.size.toLocaleString()} imported images, including every imported interval interior. This may be a large private ZIP.`;
  }
  message += ' Selected images are not proof of viewing or medical findings.';
  if (selected.size > 250) message += ' This selection exceeds the 250-image export limit.';
  $('exportEvidenceSummary').textContent = message;
}
async function loadSaved() {
  const saved = await api(`${base()}/saved`); clearEvidenceAudit(); state.savedFrameCount = saved.length;
  state.savedPositions = saved.map(item => item.position);
  renderExportEvidence();
  $('savedCount').textContent = saved.length;
  $('exportBtn').disabled = saved.length === 0 && state.intervals.length === 0;
  syncControls();
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
  state.intervals = await api(`${base()}/intervals`); clearEvidenceAudit();
  $('intervalCount').textContent = state.intervals.length;
  renderExportEvidence();
  $('exportBtn').disabled = state.savedFrameCount === 0 && state.intervals.length === 0;
  syncControls();
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
$('auditBtn').addEventListener('click', async () => {
  stopPlayback();
  if (!state.study || state.auditBusy || !(await saveReview())) return;
  const studyId = state.study.id;
  state.auditBusy = true; syncControls(); clearError();
  $('auditReport').hidden = false;
  $('auditReport').textContent = 'Verifying exported image bytes, saved revisions and interval evidence…';
  try {
    const report = await api(`/api/studies/${studyId}/evidence-audit`);
    if (!report.audit_passed || state.study?.id !== studyId) throw new Error('Local evidence verification did not complete.');
    const chosen = report.selected_position_coverage;
    const uniform = report.uniform_reference_position_coverage_at_exact_same_workload;
    const omitted = report.interval_interior_images_not_exported;
    $('auditReport').textContent =
      `Export evidence verified locally: ${report.selected_export_images.toLocaleString()} of ${report.imported_images.toLocaleString()} imported images selected; ` +
      `${report.explicitly_saved_images.toLocaleString()} explicitly saved, ${report.interval_boundary_images.toLocaleString()} interval boundaries. ` +
      `${omitted.toLocaleString()} imported ${omitted === 1 ? 'image' : 'images'} strictly inside marked intervals ${omitted === 1 ? 'was' : 'were'} NOT exported. ` +
      `At identical selected-image workload, maximum distance to a selected imported position: ${chosen.maximum_nearest_selected_imported_positions} ` +
      `versus uniform ${uniform.maximum_nearest_selected_imported_positions}. ` +
      'These are ordinal imported-position distances, not pathology detection, verified recording time or medical review completeness.';
  } catch (error) {
    $('auditReport').textContent = 'Evidence verification did not pass; no verified receipt is available.';
    fail(error);
  } finally { state.auditBusy = false; syncControls(); }
});
$('fullSpanBtn').addEventListener('click', async () => {
  stopPlayback();
  if (!state.study || !state.intervals.length || !(await saveReview())) return;
  const studyId = state.study.id;
  const proceed = window.confirm(
    'Export ALL imported images inside marked intervals, plus explicitly saved images? ' +
    'This separate ZIP can be large and may contain private images, reviewer notes and image identities. ' +
    'Exporting does not mean each image was human-reviewed or that every original video frame was imported.'
  );
  if (!proceed || state.study?.id !== studyId) return;
  const link = document.createElement('a');
  link.href = `/api/studies/${studyId}/full-span-export`;
  link.download = 'full-span-evidence.zip';
  link.click();
  announce('Full-span evidence download requested. The local server verifies the ZIP before delivery.');
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
    state.study = await api(base()); await navigate(state.frame.position, true); await loadPriorityRuns(); announce('Model output imported; reviewer notes are unchanged.');
  } catch (e) {fail(e);} finally {$('predictionFile').value = '';}
});

function resetPriorityDisplay() {
  state.priorityQuery = null;
  state.priorityData = null;
  $('prioritySelected').textContent = 'No queue';
  $('priorityItems').replaceChildren();
  $('priorityPage').textContent = '';
  $('priorityComparison').textContent = 'Build a queue to inspect omitted imported spans across all four policies.';
  $('prioritySummary').textContent = state.prioritySources.length
    ? 'Choose an exact image count and build a research-only, label-blind queue.'
    : 'Import a model prediction label with a score for every imported image.';
  syncControls();
}
async function loadPriorityRuns() {
  state.prioritySources = [];
  resetPriorityDisplay();
  if (!state.study) return;
  const available = await api(base() + '/priority-runs');
  $('prioritySource').replaceChildren();
  for (const run of available) {
    for (const label of run.labels) {
      if (!label.complete) continue;
      const index = state.prioritySources.length;
      state.prioritySources.push({run: run.run, label: label.name});
      const option = textElement('option', run.model_name + ' · ' + label.name +
        ' (' + run.imported_images.toLocaleString() + ' scored)');
      option.value = String(index);
      $('prioritySource').append(option);
    }
  }
  $('priorityCount').max = String(state.study.frame_count);
  // No fixed 10% quota, forced shortlist or hidden review-workload cap.
  $('priorityCount').value = String(state.study.frame_count);
  resetPriorityDisplay();
}
function renderPriorityComparison(report, expectedStudyId) {
  if (state.study?.id !== expectedStudyId) return;
  const names = {
    score: 'Highest model scores',
    score_diverse: 'Score + ordinal separation',
    score_bin: 'Top score per chronology bin',
    uniform: 'Uniform baseline',
  };
  const holder = $('priorityComparison');
  holder.replaceChildren();
  const table = document.createElement('table');
  table.className = 'priority-comparison-table';
  const caption = textElement('caption',
    'Each policy reviews exactly ' + report.selected_images_per_method.toLocaleString() +
    ' of ' + report.imported_images.toLocaleString() + ' imported images.');
  table.append(caption);
  const head = document.createElement('thead');
  const heading = document.createElement('tr');
  for (const title of ['Policy', 'Worst nearest-position gap', 'Longest omitted span', 'Inspect']) {
    const cell = textElement('th', title);
    cell.scope = 'col';
    heading.append(cell);
  }
  head.append(heading);
  table.append(head);
  const body = document.createElement('tbody');
  for (const policy of report.methods) {
    const row = document.createElement('tr');
    if (policy.method === $('priorityMethod').value) row.className = 'comparison-active';
    const name = textElement('th', names[policy.method] || policy.method);
    name.scope = 'row';
    row.append(name);
    row.append(textElement('td',
      String(policy.selected_ordinal_coverage.maximum_nearest_selected_imported_positions)));
    const gap = policy.largest_unselected_span;
    row.append(textElement('td', gap
      ? gap.imported_images_not_in_queue.toLocaleString() + ' imported images'
      : 'No skipped images'));
    const control = document.createElement('td');
    if (gap) {
      const button = textElement('button', 'Inspect gap', 'quiet compact');
      button.type = 'button';
      button.setAttribute('aria-label', 'Inspect largest omitted span for ' + name.textContent);
      button.addEventListener('click', () => {
        if (state.study?.id !== expectedStudyId) return;
        stopPlayback();
        navigate(gap.inspect_position).catch(fail);
      });
      control.append(button);
    } else {
      control.textContent = '—';
    }
    row.append(control);
    body.append(row);
  }
  table.append(body);
  holder.append(table);
  if (report.scores_constant) {
    holder.append(textElement('p',
      'All model scores are identical; ranking differences here are not learned evidence.',
      'panel-hint'));
  }
}

async function loadPriorityPage(offset = 0) {
  if (!state.study || state.priorityBusy || !state.prioritySources.length) return;
  const studyId = state.study.id;
  let query;
  try {
    if (offset === 0 || !state.priorityQuery) {
      const index = Number($('prioritySource').value);
      const source = state.prioritySources[index];
      const count = Number($('priorityCount').value);
      if (!source || !Number.isSafeInteger(count) || count < 1 ||
          count > state.study.frame_count) throw new Error('Choose a number between 1 and every imported image.');
      query = {
        run: source.run, label: source.label, selected_count: count,
        method: $('priorityMethod').value,
      };
    } else {
      query = state.priorityQuery;
    }
    state.priorityBusy = true; syncControls(); clearError();
    $('prioritySummary').textContent = 'Calculating a label-blind review queue from saved model scores…';
    const params = new URLSearchParams({...query, offset, page_size: 20});
    const result = await api('/api/studies/' + studyId + '/priority?' + params);
    if (state.study?.id !== studyId) return;
    state.priorityQuery = query;
    state.priorityData = result;
    $('prioritySelected').textContent = result.selected_images.toLocaleString() + ' selected';
    const coverage = result.selected_ordinal_coverage;
    const uniform = result.uniform_ordinal_coverage_at_equal_workload;
    let message = result.selected_images.toLocaleString() + ' of ' +
      result.imported_images.toLocaleString() + ' imported frames selected. ' +
      'Maximum nearest-selected imported-position gap: ' +
      coverage.maximum_nearest_selected_imported_positions + ' versus ' +
      uniform.maximum_nearest_selected_imported_positions + ' with equal-K uniform. ' +
      'No pathology labels were consulted; no bookmarks or reviewer labels were changed.';
    if (result.scores_constant) message += ' Warning: all model scores are identical, so ordering is uninformative.';
    $('prioritySummary').textContent = message;
    if (offset === 0) {
      $('priorityComparison').textContent = 'Comparing all four policies at equal workload…';
      try {
        const cmpParams = new URLSearchParams({
          run: query.run, label: query.label, selected_count: query.selected_count,
        });
        const comparison = await api('/api/studies/' + studyId +
          '/priority-comparison?' + cmpParams);
        renderPriorityComparison(comparison, studyId);
      } catch (comparisonError) {
        if (state.study?.id === studyId) {
          $('priorityComparison').textContent =
            'Policy comparison unavailable. The selected queue remains usable.';
        }
      }
    }
    $('priorityItems').replaceChildren();
    for (const item of result.items) {
      const button = textElement('button', '', 'priority-entry');
      button.append(
        textElement('strong', '#' + item.rank.toLocaleString() +
          ' · Imported frame ' + (item.position + 1).toLocaleString()),
        textElement('small', 'Model score ' + Number(item.score).toFixed(3) +
          (result.method === 'uniform' ? ' · not used to select this frame' : '') +
          ' · Open frame without auto-saving')
      );
      button.addEventListener('click', () => {
        stopPlayback();
        navigate(item.position).catch(fail);
      });
      $('priorityItems').append(button);
    }
    const showing = result.items.length ? (result.offset + 1).toLocaleString() + '–' +
      (result.offset + result.items.length).toLocaleString() : '0';
    $('priorityPage').textContent = showing + ' of ' + result.selected_images.toLocaleString();
  } catch (error) {
    if (state.study?.id === studyId) {
      $('prioritySummary').textContent = 'Review queue could not be verified or built.';
      fail(error);
    }
  } finally {
    state.priorityBusy = false;
    syncControls();
  }
}
for (const id of ['prioritySource', 'priorityCount', 'priorityMethod']) {
  $(id).addEventListener('change', resetPriorityDisplay);
}
$('priorityBuild').addEventListener('click', () => loadPriorityPage(0));
$('priorityPrev').addEventListener('click', () => {
  if (state.priorityData) loadPriorityPage(Math.max(0, state.priorityData.offset - 20));
});
$('priorityNext').addEventListener('click', () => {
  if (state.priorityData) loadPriorityPage(state.priorityData.offset + state.priorityData.items.length);
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
    try {state.study = await api(base()); await navigate(state.frame.position, true); await loadPriorityRuns(); announce('Local model finished. Reviewer notes are unchanged.');}
    catch (error) {fail(error);}
  }
});

(async () => {
  try {const config = await api('/api/config'); state.token = config.token; $('version').textContent = `v${config.version}`;
    await refreshLibrary(); if (state.studies.length) await selectStudy(state.studies[0].id);
  } catch (e) {fail(e);}
})();

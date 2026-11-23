'use strict';
let token;
async function refresh() {
  const response = await fetch('/api/restricted/state');
  if (!response.ok) throw new Error('Cannot verify session state.');
  const state = await response.json();
  const valid = state.restricted_claim_valid;
  document.getElementById('mode').textContent = valid
    ? `RESTRICTED GENERATED SESSION · K=${state.commitment.selection.k} · frozen selection ${state.commitment_sha256}`
    : 'RESTRICTED CLAIM INVALID — mode exit or source-integrity failure. Earlier restriction cannot be restored.';
  document.getElementById('exit').disabled = !valid;
  const nav = document.getElementById('frames');
  nav.replaceChildren();
  const positions = valid ? state.commitment.selection.positions : [];
  if (!valid) document.getElementById('image').removeAttribute('src');
  for (const p of positions) {
    const button = document.createElement('button');
    button.textContent = `Frame ${p + 1}`;
    button.dataset.position = p;
    button.onclick = () => {
      document.getElementById('caption').textContent = `Generated source position ${p}; no human finding created`;
      document.getElementById('image').src = `/api/restricted/images/${p}`;
    };
    nav.append(button);
  }
  return state;
}
async function start() {
  const config = await fetch('/api/config');
  if (!config.ok) throw new Error('Authentication unavailable.');
  token = (await config.json()).token;
  const state = await refresh();
  // Only after the server has frozen and returned the selected identities.
  if (state.integrity_ok) document.querySelector('#frames button')?.click();
}
document.getElementById('exit').onclick = async () => {
  try {
    // Clear current pixels and invalidate the label before ending the session.
    document.getElementById('image').removeAttribute('src');
    document.getElementById('mode').textContent = 'ENDING RESTRICTED SESSION — no further restricted claim.';
    const response = await fetch('/api/restricted/exit', {method: 'POST', headers: {'X-Review-Token': token}});
    if (!response.ok) throw new Error('Exit could not be recorded; omitted images remain blocked.');
    await refresh();
  } catch (error) { document.getElementById('error').textContent = error.message; }
};
document.getElementById('image').onerror = async () => {
  document.getElementById('error').textContent = 'Image delivery failed; inspect session receipt.';
  try { await refresh(); } catch (error) { document.getElementById('error').textContent = error.message; }
};
start().catch(error => { document.getElementById('error').textContent = error.message; });

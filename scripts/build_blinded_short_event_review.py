"""Create a private, source-verified, label-blinded original-image review packet.

Research-only selected-case pilot; NOT independent clinical validation. Neither the
reviewer packet nor local HTML contains any source IDs, source blood labels, pair
roles, model scores, patient groups or network interaction. A distinct private
escrow ZIP holds the mapping and all provenance. No transfer is performed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import random
import re
import secrets
import zipfile
from PIL import Image

SUPPORTED_EXAMS = (23, 25, 29, 30)
EXPECTED_RUNS = {23: 23, 25: 20, 29: 11, 30: 15}
EXPECTED_SINGLETONS = 21
NAME = re.compile(r'^images/(0?\d{2,3})/frame_(\d{6})\.PNG$')


def sha(data: bytes) -> str:
    return sha256(data).hexdigest()


def canonical_json(obj: object) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode('utf-8')


def verify_cohort(manifest: dict, *, expected_pairs: int = 69) -> tuple[list[dict], dict[int, dict]]:
    if not isinstance(manifest, dict) or not isinstance(manifest.get('images'), list) or not isinstance(manifest.get('pairs'), list):
        raise ValueError('The original private short-event manifest is missing images/pairs.')
    pairs = manifest['pairs']; images = manifest['images']
    if len(pairs) != expected_pairs:
        raise ValueError('Short-event pair count changed.')
    if expected_pairs == 69 and (Counter(int(p['exam']) for p in pairs) != EXPECTED_RUNS or
                                 sum(p['run_length'] == 1 for p in pairs) != EXPECTED_SINGLETONS):
        raise ValueError('Frozen 69-run examination/short-event support changed.')
    references: dict[int, dict] = {}
    seen_runs = set()
    for p in pairs:
        if type(p) is not dict or set(p) != {'exam', 'run_id', 'run_length', 'positive_index', 'negative_index'}:
            raise ValueError('Unexpected pair record or private extra field.')
        ex, run_id, run_len = p['exam'], p['run_id'], p['run_length']
        if not all(type(v) is int for v in (ex, run_id, run_len)) or ex not in SUPPORTED_EXAMS or run_id < 0 or not 1 <= run_len <= 5:
            raise ValueError('Invalid examination/run key or native run length.')
        if (ex, run_id) in seen_runs:
            raise ValueError('Duplicate original source event run.')
        seen_runs.add((ex, run_id))
        for role, want in (('positive_index', 1), ('negative_index', 0)):
            ix = p[role]
            if type(ix) is not int or ix < 0 or ix >= len(images):
                raise ValueError('Invalid source image index.')
            r = images[ix]
            if (type(r) is not dict or set(r) != {'exam','frame','blood','sha256','bytes'} or
                r['exam'] != ex or r['blood'] != want or
                type(r['frame']) is not int or r['frame'] < 0 or r['frame'] % 5 != 0 or
                type(r['bytes']) is not int or r['bytes'] <= 0 or
                not isinstance(r['sha256'], str) or not re.fullmatch('[0-9a-f]{64}',r['sha256'])):
                raise ValueError('Invalid or incoherent source role / original hash.')
            if ix in references and references[ix] != r:
                raise ValueError('Contradictory endpoint source identity.')
            references[ix] = r
        if p['positive_index'] == p['negative_index']:
            raise ValueError('A pair cannot reference the same original image.')
        pos, neg = (images[p['positive_index']], images[p['negative_index']])
        # Native stride-5 source neighbours are already frozen. No artificial neighbours.
        if abs(pos['frame'] - neg['frame']) != 5:
            raise ValueError('Pair was not an original stride-five source neighbour.')
    if len({(r['exam'],r['frame']) for r in references.values()}) != len(references):
        raise ValueError('One original source identity has multiple image indices.')
    if len({r['sha256'] for r in references.values()}) != len(references):
        raise ValueError('Duplicated source image bytes across endpoints.')
    if expected_pairs == 69 and len(references) != 137:
        raise ValueError('Frozen distinct original endpoint count changed.')
    return pairs, references


def _read_source_archive(path: Path, needed: set[tuple[int, int]], found: dict) -> dict:
    # Outer archive may contain exactly one inner private verified source ZIP.
    info = {'file': path.name, 'size_bytes': path.stat().st_size,
            'sha256': sha(path.read_bytes()), 'selected_members': 0}
    with zipfile.ZipFile(path) as outer:
        inner_names = [n for n in outer.namelist() if n.endswith('.zip')]
        if len(inner_names) == 1:
            archive = zipfile.ZipFile(BytesIO(outer.read(inner_names[0])))
        elif len(inner_names) == 0:
            archive = outer
        else:
            raise ValueError('Ambiguous nested original-source archive.')
        try:
            for member in archive.infolist():
                m=NAME.fullmatch(member.filename)
                if not m:
                    continue
                key=(int(m.group(1)), int(m.group(2)))
                if key not in needed:
                    continue
                raw=archive.read(member)
                if key in found:
                    if found[key] != raw:
                        raise ValueError('Conflicting publisher bytes across retained sources.')
                else:
                    found[key]=raw
                info['selected_members']+=1
        finally:
            if archive is not outer:
                archive.close()
    return info


def fetch_verified_sources(records: dict[int,dict], archive_paths: list[Path], allowed_hashes: dict[str,str] | None = None) -> tuple[dict[tuple[int,int],bytes],list[dict]]:
    needed={(r['exam'],r['frame']) for r in records.values()}
    found: dict[tuple[int,int],bytes]={}; archives=[]
    if len({p.name for p in archive_paths}) != len(archive_paths):
        raise ValueError('Ambiguous archive basenames in the input selection.')
    for path in archive_paths:
        if not path.is_file():
            raise ValueError('Missing original-source package.')
        item=_read_source_archive(path,needed,found)
        if allowed_hashes is not None and allowed_hashes.get(item['file']) != item['sha256']:
            raise ValueError('Source package failed pinned expected SHA-256: '+item['file'])
        archives.append(item)
    if set(found) != needed:
        raise ValueError('Not all original-source endpoints are retained: '+str(len(needed-set(found))))
    for r in records.values():
        raw=found[(r['exam'],r['frame'])]
        if len(raw)!=r['bytes'] or sha(raw)!=r['sha256']:
            raise ValueError('Original medical source byte/identity mismatch.')
        # Reject malformed, cropped or non-original images even though source was hash-verified.
        with Image.open(BytesIO(raw)) as im:
            if im.format != 'PNG' or im.size != (512,512) or im.mode != 'RGB':
                raise ValueError('Unexpected original source image geometry/encoding.')
            im.verify()
    return found,archives


def pixel_identical_deidentified_png(raw: bytes) -> tuple[bytes,str]:
    # Rebuild from pixels: convert() alone can retain ancillary data such as ICC.
    with Image.open(BytesIO(raw)) as im:
        pix=im.convert('RGB').tobytes()
        image=Image.frombytes('RGB',im.size,pix)
    output=BytesIO();image.save(output,format='PNG',optimize=False)
    data=output.getvalue()
    with Image.open(BytesIO(data)) as reread:
        if reread.size!=(512,512) or reread.mode!='RGB' or sha(reread.tobytes())!=sha(pix):
            raise ValueError('Viewer conversion changed original pixel content.')
    return data,sha(pix)


def build_packet(manifest: dict, found: dict, archives: list[dict],
                 *, manifest_sha: str, expected_pairs: int = 69,
                 deterministic_ids: dict[int,str] | None = None, packet_id: str | None = None) -> tuple[bytes,bytes,dict]:
    pairs,records=verify_cohort(manifest,expected_pairs=expected_pairs)
    if len(found)!=len(records):
        raise ValueError('Unexpected input image count.')
    packet_id=packet_id or secrets.token_hex(12)
    if not re.fullmatch('[a-f0-9]{24}',packet_id):
        raise ValueError('Invalid opaque packet identifier.')
    entry_ids={ix:deterministic_ids[ix] if deterministic_ids else secrets.token_hex(12) for ix in records}
    if len(set(entry_ids.values()))!=len(entry_ids) or any(not re.fullmatch('[a-f0-9]{24}',x) for x in entry_ids.values()):
        raise ValueError('Invalid or duplicated opaque image identifier.')
    order=list(records)
    secrets.SystemRandom().shuffle(order) if deterministic_ids is None else random.Random(77).shuffle(order)
    reviewer_items=[]; mapping=[]; output_images={}
    for ix in order:
        r=records[ix]; raw=found[(r['exam'],r['frame'])]
        if sha(raw)!=r['sha256'] or len(raw)!=r['bytes']:
            raise ValueError('Endpoint bytes no longer match the original source.')
        png,pixel_sha=pixel_identical_deidentified_png(raw)
        key=entry_ids[ix]
        output_images[f'images/{key}.png']=png
        reviewer_items.append({'item_id':key,'image':f'images/{key}.png'})
        mapping.append({'item_id':key,'source_exam':r['exam'],'source_frame':r['frame'],
                        'published_blood_label':r['blood'],'original_png_sha256':r['sha256'],
                        'original_png_bytes':r['bytes'],'retained_pixel_sha256':pixel_sha,
                        'review_png_sha256':sha(png)})
    public_manifest={'schema_version':'capsule-review-blinded-single-image-v1','packet_id':packet_id,
                     'intentionally_selected_development_only':True,'number_of_images':len(reviewer_items),
                     'items':reviewer_items}
    escrow={'schema_version':'capsule-review-private-adjudication-key-v1','packet_id':packet_id,
            'source_manifest_sha256':manifest_sha,'images':mapping,
            'pairs':[{'source_exam':p['exam'],'source_run_id':p['run_id'],'run_length':p['run_length'],
                      'published_positive_item_id':entry_ids[p['positive_index']],
                      'published_negative_item_id':entry_ids[p['negative_index']]}
                     for p in pairs],
            'source_archives':archives,
            'restrictions':{'training_or_test_use':'Do not treat as independent or prospectively sampled test; labels/selection were previously inspected.',
                            'patient_independence':'UNVERIFIED','clinical_reference_truth':'UNVERIFIED',
                            'external_sharing':'Not performed by tool; assess permissions/ethics before sharing.'}}
    reviewer_readme='''# Capsule Review — private blinded single-image pilot\n\nThis private research packet contains 137 selected source-original capsule images from four previously inspected development examinations. It does NOT constitute an independent or representative clinical dataset. All images are provided in randomized order with opaque IDs. Original source IDs, dataset labels, pair memberships, model scores and any model error status are in a separate private escrow NOT included here.\n\n## Reviewer procedure\n1. Extract the complete ZIP to a private, access-controlled folder. Open `index.html` in a browser offline. Never host or upload the folder to any site or external service.\n2. Enter a pseudonymous reviewer code only, not a name or patient identifier.\n3. Score each isolated original image independently: visible fresh blood; hematin/old blood; suspected lookalike or artefact; image quality; and whether temporal context is required. Use *uncertain* rather than guessing. Do not infer diagnosis, lesion identity or activity from a single frame.\n4. Export the JSON locally. Use Import JSON to resume. Save the response in private storage; no scores are sent anywhere.\n5. For independent dual review, each reviewer uses a separate copy and reviewer code. Disagreements require a separate predeclared adjudication step by a qualified expert.\n\nImages are pixel-identical, metadata-stripped copies of the verified original Galar PNGs. Exact original hashes and source provenance reside ONLY in the private escrow. Reviewer responses are not a validated clinical reference standard until adjudication.\n\n**Dataset attribution:** Le Floch et al., *Galar — a large multi-label video capsule endoscopy dataset*, Scientific Data (2025), DOI 10.1038/s41597-025-05112-7, CC BY 4.0. This prototype is research-only and not a medical device. Do not circulate the images without confirming applicable study agreements and research permissions.\n'''
    script = make_review_javascript()
    html = make_review_html(packet_id)
    buf=BytesIO()
    with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr('index.html',html);z.writestr('review.js',script)
        z.writestr('manifest.json',canonical_json(public_manifest));z.writestr('packet-data.js', 'window.REVIEW_PACKET = '+json.dumps(public_manifest,separators=(',',':'))+';\n');z.writestr('README.md',reviewer_readme)
        for name,png in output_images.items():z.writestr(name,png)
    reviewer=buf.getvalue();escrow['reviewer_zip_sha256']=sha(reviewer)
    key=BytesIO()
    with zipfile.ZipFile(key,'w',compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('PRIVATE_KEY.json',canonical_json(escrow))
    key_bytes=key.getvalue()
    receipt={'schema_version':'capsule-review-clinical-review-prep-v1','status':'PREPARED_NOT_CLINICALLY_REVIEWED',
             'packet_id':packet_id,'selected_original_images':len(records),'pairs':len(pairs),
             'reviewer_zip_sha256':sha(reviewer),'private_key_zip_sha256':sha(key_bytes),
             'source_manifest_sha256':manifest_sha,'model_training_performed':False,
             'original_source_images_modified':False,'pixel_identical_metadata_stripped':True,
             'disclosure':'No external distribution performed and no clinical adjudication exists.'}
    return reviewer,key_bytes,receipt


def make_review_html(packet_id:str)->str:
    return '''<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'none'; form-action 'none'">
<title>Capsule Review · Blinded Image Adjudication</title><style>
:root{font-family:system-ui,sans-serif;color-scheme:light}body{margin:auto;max-width:1000px;padding:18px;color:#192536;background:#f4f6f9}header,.panel{background:white;border-radius:12px;padding:20px;margin-bottom:15px;border:1px solid #e0e5ec}h1{font-size:1.5rem;margin:0 0 10px}label,legend{font-weight:600}button{border:1px solid #bbc7d4;border-radius:8px;padding:12px;background:#fff;cursor:pointer}button:focus,input:focus,select:focus{outline:3px solid #487ad0}button.primary{background:#164785;color:white}.imageWrap{text-align:center}img{max-width:min(95%,512px);width:auto;height:auto;border:1px solid #d1dce7}fieldset{border:1px solid #dae2ea;border-radius:8px;margin:14px 0;padding:12px}.choices{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px}.choices label{font-weight:400;white-space:nowrap}textarea{width:100%;min-height:60px;box-sizing:border-box}footer{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap}.muted{color:#53657b;font-size:.92rem}#status{font-weight:600}#viewer{display:none}.visually-hidden{position:absolute;left:-9999px}
</style></head><body><header><h1>Capsule Review · Blinded image review</h1><p class="muted">Research pilot only. No model predictions, source IDs or original labels are shown. No clinical diagnosis or validated ground truth is implied. Offline only; do not upload clinical images.</p><p class="muted">Packet: '''+packet_id+'''</p></header>
<section class="panel"><label for="reviewer">Pseudonymous reviewer code</label> <input id="reviewer" maxlength="40" placeholder="e.g. reviewer-A" aria-describedby="reviewerHelp"><p id="reviewerHelp" class="muted">Enter a code before answering. It locks when you begin. Each reviewer must start in a separate tab without another reviewer's answers. No names or patient identifiers. Export often.</p><button id="export" class="primary">Export reviewed JSON</button> <label for="restore" class="muted">Restore saved JSON:</label> <input id="restore" type="file" accept=".json,application/json"><p id="status" aria-live="polite"></p></section>
<main id="viewer" class="panel"><h2 id="progress"></h2><div class="imageWrap"><img id="scan" alt="Unlabelled capsule endoscopy research image" width="512" height="512"></div><form id="answers">
<fieldset><legend>Visible fresh blood in this image?</legend><div class="choices" data-field="fresh_blood"></div></fieldset>
<fieldset><legend>Hematin / old blood appearance?</legend><div class="choices" data-field="hematin"></div></fieldset>
<fieldset><legend>Suspected red-colour lookalike or image artefact?</legend><div class="choices" data-field="artifact"></div></fieldset>
<fieldset><legend>Image quality</legend><div class="choices" data-field="image_quality"></div></fieldset>
<fieldset><legend>Temporal context necessary to decide?</legend><div class="choices" data-field="needs_context"></div></fieldset>
<label for="note">Brief rationale or uncertainty (no identifying details)</label><textarea id="note" maxlength="240"></textarea></form>
<footer><button id="previous">Previous image</button><button id="next" class="primary">Save and next image</button></footer></main>
<script src="packet-data.js"></script><script src="review.js"></script></body></html>'''


def make_review_javascript()->str:
    # This is local-only application code; no fetch, XMLHTTPRequest, WebSocket, analytics or storage.
    return r'''"use strict";
const SETS={fresh_blood:["yes","no","uncertain"],hematin:["yes","no","uncertain"],artifact:["yes","no","uncertain"],image_quality:["adequate","limited","uninterpretable"],needs_context:["yes","no","uncertain"]};
const fieldNames=Object.keys(SETS);
let data=null,at=0,responses={},boundReviewer=null,dirty=false;
const $=(id)=>document.getElementById(id);
const fail=(message)=>{$("status").textContent=message;};
const validCode=(code)=>typeof code==="string"&&/^[A-Za-z0-9_-]{2,40}$/.test(code);
const isRecord=(value)=>value!==null&&typeof value==="object"&&!Array.isArray(value);
function updateEditor(){
  const enabled=boundReviewer!==null||validCode($("reviewer").value.trim());
  document.querySelectorAll("#answers input, #note").forEach(input=>input.disabled=!enabled);
}
function bindReviewer(code){
  boundReviewer=code;$("reviewer").value=code;$("reviewer").readOnly=true;updateEditor();
}
function recordEdit(){
  if(boundReviewer===null){
    const code=$("reviewer").value.trim();
    if(!validCode(code))return;
    bindReviewer(code);
  }
  dirty=true;
}
async function init(){
  // No network call: JSON is included as an adjacent local script below instead of fetched.
  if(!window.REVIEW_PACKET||!Array.isArray(window.REVIEW_PACKET.items)) {fail("Missing packet script. Extract the entire ZIP and open index.html locally.");return;}
  data=window.REVIEW_PACKET;
  if(data.number_of_images!==data.items.length||new Set(data.items.map(x=>x.item_id)).size!==data.items.length){fail("Invalid research packet.");return;}
  for(const field of fieldNames){const root=document.querySelector('[data-field="'+field+'"]');
    for(const opt of SETS[field]){let label=document.createElement("label"),input=document.createElement("input");input.type="radio";input.name=field;input.value=opt;label.append(input,document.createTextNode(" "+opt));root.append(label);}}
  $("viewer").style.display="block";updateEditor();render();
}
function saveCurrent(){
  if(!data)return;
  const item=data.items[at];let ans={};
  for(const field of fieldNames){const selected=document.querySelector('input[name="'+field+'"]:checked');ans[field]=selected?selected.value:null;}
  ans.note=$("note").value.slice(0,240);
  if(fieldNames.some(f=>ans[f]!==null)||ans.note)responses[item.item_id]=ans;
  else delete responses[item.item_id];
}
function render(){
  const item=data.items[at];$("progress").textContent="Image "+(at+1)+" / "+data.items.length;
  $("scan").src=item.image;$("scan").alt="Blinded research source image "+(at+1);
  let ans=responses[item.item_id]||{};
  for(const field of fieldNames){document.querySelectorAll('input[name="'+field+'"]').forEach(x=>x.checked=(x.value===ans[field]));}
  $("note").value=ans.note||"";
  $("previous").disabled=at===0;$("next").textContent=at===data.items.length-1?"Save final image":"Save and next image";
  fail(Object.keys(responses).length+" image(s) have saved responses in this browser session. Export JSON to preserve them.");
}
function download(){
  if(!data)return;
  const reviewer=boundReviewer||$("reviewer").value.trim();
  if(!validCode(reviewer)){fail("Enter a pseudonymous reviewer code (2–40 letters, numbers, _ or -).");return;}
  bindReviewer(reviewer);saveCurrent();
  let out={schema_version:"capsule-review-blinded-response-v1",packet_id:data.packet_id,reviewer_code:reviewer,responses,exported_at:new Date().toISOString()};
  let blob=new Blob([JSON.stringify(out,null,2)+"\n"],{type:"application/json"});let url=URL.createObjectURL(blob);
  let anchor=document.createElement("a");anchor.href=url;anchor.download="capsule-review-"+data.packet_id+"-"+reviewer+".json";document.body.append(anchor);anchor.click();anchor.remove();URL.revokeObjectURL(url);
  dirty=false;
  fail("Local JSON exported; " + Object.keys(responses).length + " of " + data.number_of_images + " images recorded. Keep it private.");
}
function restore(file){if(!file||!data)return;fail("Reading saved JSON...");let reader=new FileReader();reader.onload=()=>{
 try{
   // Restore only into an untouched session. Never replace or merge a reader's work.
   if(boundReviewer!==null||dirty||Object.keys(responses).length)throw new Error("Open a new tab to restore JSON; this session already has a review.");
   const obj=JSON.parse(reader.result),ids=new Set(data.items.map(x=>x.item_id));
   if(!isRecord(obj)||obj.schema_version!=="capsule-review-blinded-response-v1"||obj.packet_id!==data.packet_id||!isRecord(obj.responses))throw new Error("Wrong packet or response schema.");
   if(!validCode(obj.reviewer_code))throw new Error("Invalid reviewer code.");
   for(const [id,answer] of Object.entries(obj.responses)){
     if(!ids.has(id)||!isRecord(answer)||Object.keys(answer).length!==fieldNames.length+1||Object.keys(answer).some(k=>![...fieldNames,"note"].includes(k)))throw new Error("Unexpected response key.");
     for(const field of fieldNames)if(answer[field]!==null&&!SETS[field].includes(answer[field]))throw new Error("Invalid response value.");
     if(typeof answer.note!=="string"||answer.note.length>240)throw new Error("Invalid note.");
   }
   responses=obj.responses;bindReviewer(obj.reviewer_code);at=0;dirty=false;render();
 }catch(error){fail("Cannot restore: "+error.message);}
 };reader.onerror=()=>fail("Cannot restore: file could not be read.");reader.readAsText(file);}
$("reviewer").addEventListener("input",updateEditor);
$("answers").addEventListener("input",recordEdit);
$("answers").addEventListener("submit",event=>event.preventDefault());
$("previous").addEventListener("click",()=>{saveCurrent();if(at>0)--at;render();});
$("next").addEventListener("click",()=>{saveCurrent();if(at<data.items.length-1)++at;render();});
$("export").addEventListener("click",download);
$("restore").addEventListener("change",(event)=>{restore(event.target.files[0]);event.target.value="";});
window.addEventListener("beforeunload",(event)=>{if(dirty){event.preventDefault();event.returnValue="";}});
// packet-data.js is loaded as a local static script, never fetched.
init();'''


def main() -> None:
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--foundation-evidence-zip',type=Path,required=True)
    cli.add_argument('--archive',type=Path,action='append',required=True,help='Previously retained publisher-original package, repeatable')
    cli.add_argument('--output-dir',type=Path,required=True)
    cli.add_argument('--archive-hashes-json',type=Path,help='Optional exact filename-to-SHA256 trusted private dependency map')
    args=cli.parse_args()
    if args.output_dir.exists():raise FileExistsError('Refuse to overwrite an existing review packet directory.')
    with zipfile.ZipFile(args.foundation_evidence_zip) as z:
        b=z.read('foundation/support-manifest-private.json')
    source=json.loads(b);_,records=verify_cohort(source)
    expected=json.loads(args.archive_hashes_json.read_text()) if args.archive_hashes_json else None
    data,archive_receipts=fetch_verified_sources(records,args.archive,expected)
    review,key,receipt=build_packet(source,data,archive_receipts,manifest_sha=sha(b))
    args.output_dir.mkdir(parents=True)
    (args.output_dir/'REVIEWER_BLINDED_ORIGINAL_IMAGES.zip').write_bytes(review)
    (args.output_dir/'PRIVATE_UNBLINDING_KEY.zip').write_bytes(key)
    (args.output_dir/'PREPARATION_RECEIPT.json').write_bytes(canonical_json(receipt))
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()

"""Verify local full-span archive against trusted study manifest."""
import argparse
import json
from pathlib import Path
from capsule_review.full_span_evidence import verify_full_span_evidence

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--study-manifest",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    x=p.parse_args()
    if x.output.exists():
        raise FileExistsError("Output exists.")
    if x.study_manifest.stat().st_size>64*1024*1024:
        raise ValueError("Manifest size exceeds limit.")
    result=verify_full_span_evidence(x.archive,json.loads(x.study_manifest.read_text()))
    x.output.parent.mkdir(parents=True,exist_ok=True)
    with x.output.open("x",encoding="utf-8") as f:
        json.dump(result,f,indent=2,sort_keys=True,allow_nan=False)
        f.write("\n")
    print("Full-span evidence verified; exported images:",result["exported_images"])

if __name__=="__main__":
    main()

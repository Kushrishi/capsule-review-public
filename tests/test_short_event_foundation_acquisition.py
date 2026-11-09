import sys
from pathlib import Path
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from acquire_short_event_foundation import validate_range, private

def test_no_full_download_or_shifted_range_fallback():
    validate_range(206,'bytes 10-19/100',10,10,100)
    for status,header in [(200,'bytes 10-19/100'),(206,'bytes 11-20/100'),(206,'bytes 10-19/101'),(206,None)]:
        with pytest.raises(ValueError):validate_range(status,header,10,10,100)

def test_private_source_path_refused_in_public_repo():
    with pytest.raises(ValueError):private(Path(__file__))

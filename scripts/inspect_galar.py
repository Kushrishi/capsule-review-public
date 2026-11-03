"""Compatibility entry point for a metadata-only Galar inspection."""
import sys
from capsule_review.cli import main

if __name__ == '__main__':
    sys.argv[1:1] = ['data', 'catalog']
    main()

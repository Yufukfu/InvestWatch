import sys

from iw_scraper.app import main

main(sys.argv[1] if len(sys.argv) > 1 else "")

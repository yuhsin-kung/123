# Vendored copies of /workspace/scu-events/scu_common.py and scrape_events.py.
# The Django command only uses their *fetch/parse* functions; storage goes through the ORM.
# (scrape_events.py does `import scu_common as C`; the sys.path tweak below keeps that working.)
import os, sys
sys.path.insert(0, os.path.dirname(__file__))

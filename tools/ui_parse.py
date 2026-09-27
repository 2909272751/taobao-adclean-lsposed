#!/usr/bin/env python3
"""Parse a uiautomator dump XML and print a compact, greppable node list.

Usage:
  python tools/ui_parse.py scratch-recon/ui/foo-ui.xml            # all nodes with text/id/desc
  python tools/ui_parse.py scratch-recon/ui/foo-ui.xml --all      # include id-only nodes
  python tools/ui_parse.py scratch-recon/ui/foo-ui.xml --grep ad  # filter on any field
"""
import argparse
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('xml')
    ap.add_argument('--all', action='store_true', help='include nodes without text/desc')
    ap.add_argument('--grep', default=None)
    ap.add_argument('--ids-only', action='store_true', help='print only resource-id values')
    args = ap.parse_args()

    tree = ET.parse(Path(args.xml))
    root = tree.getroot()
    n = 0
    for node in root.iter('node'):
        a = node.attrib
        text = a.get('text', '')
        desc = a.get('content-desc', '')
        rid = a.get('resource-id', '')
        cls = a.get('class', '')
        bounds = a.get('bounds', '')
        clickable = a.get('clickable', '')
        if args.ids_only:
            if rid:
                print(rid)
            continue
        if not args.all and not text and not desc and not rid:
            continue
        line = '\t'.join([cls, rid, text, desc, bounds, 'click=' + clickable])
        if args.grep and not re.search(args.grep, line, re.I):
            continue
        print(line)
        n += 1
    if args.ids_only:
        return
    print(f'# {n} nodes', flush=True)


if __name__ == '__main__':
    main()

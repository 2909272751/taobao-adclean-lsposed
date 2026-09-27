#!/usr/bin/env python3
"""Inspect / enable / scope the LSPosed modules_config.db for this module.

LSPosed 1.8.x keeps module enable + scope in modules_config.db:
  scope       (mid, app_pkg_name, user_id)
  modules     (mid, module_pkg_name, apk_path, enabled, ...)

Usage:
  python tools/lspd_db.py inspect  <db>
  python tools/lspd_db.py enable   <db> <module_pkg> <comma-separated-targets>
"""
import sqlite3
import sys


def dump(db):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    for (name, sql) in con.execute("select name, sql from sqlite_master where type='table'"):
        print('TABLE', name)
        print(' ', sql)
    print('=== modules ===')
    try:
        for row in con.execute('select * from modules'):
            print(dict(row))
    except Exception as exc:
        print('modules:', exc)
    print('=== scope ===')
    try:
        for row in con.execute('select * from scope'):
            print(dict(row))
    except Exception as exc:
        print('scope:', exc)


def enable(db, module_pkg, targets):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    row = con.execute('select * from modules where module_pkg_name=?', (module_pkg,)).fetchone()
    if row is None:
        raise SystemExit('module not registered in db: ' + module_pkg)
    mid = row['mid']
    con.execute('update modules set enabled=1 where mid=?', (mid,))
    for target in targets:
        exists = con.execute(
            'select 1 from scope where mid=? and app_pkg_name=? and user_id=0', (mid, target)).fetchone()
        if exists is None:
            con.execute('insert into scope(mid, app_pkg_name, user_id) values (?,?,0)', (mid, target))
    con.commit()
    print('enabled mid=%s module=%s' % (mid, module_pkg))
    for r in con.execute('select * from scope where mid=?', (mid,)):
        print('scope', dict(r))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    action = sys.argv[1]
    if action == 'inspect':
        dump(sys.argv[2])
    elif action == 'enable':
        enable(sys.argv[2], sys.argv[3], sys.argv[4].split(','))
    else:
        raise SystemExit('unknown action ' + action)

INSERT OR IGNORE INTO modules_state(module_pkg_name, user_id, enabled, scope_request_blocked)
VALUES ('io.github.taobaoadclean', 0, 1, 0);
UPDATE modules_state SET enabled = 1 WHERE module_pkg_name = 'io.github.taobaoadclean' AND user_id = 0;
INSERT OR IGNORE INTO scope(module_pkg_name, app_pkg_name, user_id) VALUES ('io.github.taobaoadclean', 'com.taobao.idlefish', 0);
INSERT OR IGNORE INTO scope(module_pkg_name, app_pkg_name, user_id) VALUES ('io.github.taobaoadclean', 'com.taobao.taobao', 0);
SELECT module_pkg_name, user_id, enabled FROM modules_state WHERE module_pkg_name = 'io.github.taobaoadclean';
SELECT module_pkg_name, app_pkg_name FROM scope WHERE module_pkg_name = 'io.github.taobaoadclean';

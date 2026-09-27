.mode list
select 'STATE ' || module_pkg_name || ' user=' || user_id || ' enabled=' || enabled || ' blk=' || scope_request_blocked from modules_state where module_pkg_name in ('io.github.taobaoadclean','io.github.didiadclean');
select 'SCOPE ' || module_pkg_name || ' -> ' || app_pkg_name from scope where module_pkg_name in ('io.github.taobaoadclean','io.github.didiadclean');
select 'MOD ' || module_pkg_name || ' path=' || apk_path from modules where module_pkg_name in ('io.github.taobaoadclean','io.github.didiadclean');

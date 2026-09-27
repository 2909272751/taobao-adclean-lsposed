.mode list
select 'STATE ' || module_pkg_name || ' user=' || user_id || ' enabled=' || enabled from modules_state where module_pkg_name = 'io.github.taobaoadclean';
select 'SCOPE ' || app_pkg_name from scope where module_pkg_name = 'io.github.taobaoadclean';

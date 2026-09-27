.mode list
select 'CONFIG ' || group_name || ' / ' || key_name || ' = ' || hex(data) from module_configs where module_pkg_name = 'io.github.taobaoadclean';

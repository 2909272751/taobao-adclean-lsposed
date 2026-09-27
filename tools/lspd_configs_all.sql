.mode list
select 'ROW ' || module_pkg_name || ' / ' || group_name || ' / ' || key_name || ' = ' || hex(data) from module_configs order by module_pkg_name limit 40;

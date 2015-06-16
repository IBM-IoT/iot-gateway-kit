database sysadmin;
grant dba to root;

execute function admin('STORAGEPOOL ADD', '$INFORMIXDIR/storage',
			0,0,'64MB',1);
execute function admin('CREATE DBSPACE FROM STORAGEPOOL',
			'datadbs1', '100 MB');
execute function admin('CREATE TEMPDBSPACE FROM STORAGEPOOL',
			'tmpdbspace', '50 MB');

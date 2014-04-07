# Apache Configuration

Here's some tips on getting Rophako set up on Apache.

# mod\_fcgid and mod\_rewrite

For kirsle.net I needed to set it up using `mod_fcgid` because my site has a lot
of legacy URLs to old static files, so Rophako needs to serve the main website
pages and Apache needs to serve everything else.

* Apache configuration:

```apache
# Rophako www.kirsle.net
<VirtualHost *:80>
    ServerName www.kirsle.net
    DocumentRoot /home/kirsle/www
    CustomLog /home/kirsle/logs/access_log combined
    ErrorLog /home/kirsle/logs/error_log
    SuexecUserGroup kirsle kirsle

    <Directory "/home/kirsle/www">
        Options Indexes FollowSymLinks ExecCGI
        AllowOverride All
        Order allow,deny
        Allow from all
    </Directory>

    <Directory "/home/kirsle/www/fcgi">
        SetHandler fcgid-script
        Options +ExecCGI
        AllowOverride all
        Order allow,deny
        Allow from all
    </Directory>
</VirtualHost>
```

* `~/www/.htaccess` configuration:

```apache
<IfModule mod_rewrite.c>
    RewriteEngine on
    RewriteBase /
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^(.*)$ /fcgi/index.fcgi/$1 [QSA,L]
    RewriteRule ^$ /fcgi/index.fcgi/ [QSA,L]
</IfModule>
```

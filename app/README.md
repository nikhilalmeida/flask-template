**Requirements for the dupecheck tool can be found [here](https://docs.google.com/a/demandmedia.com/document/d/1XTQkZdM0l5h3PEY1xfvqJDkLhUp43Ncq5rAarl7GjmI/edit).**

## Setup Project:
    To get started run "ENV=local make setup". This will set up the virtual environment, install all the dependencies and will create the logs directory.
    All dependencies are present in the requirements.txt
    Configurations are present in configs/*. Each environment has its own config.
    make setup will copy the appropriate environment config into configs/config_override.py
    When the app is started config.py will first load all the configurations in configs/config_local.py followed by
    configs/config_override.py

## Development:
    There are two branches. "master" and "development". Always create a new branch off of development to work in.
    When finished submit a merge request to merge branch with development.

    For rapid development with automatic code reloads, run the flask app in development mode. This can be done using
    $ ./runscript.sh app.y
    This will start the server in debug mode.

**Work In Progress. Do not use yet.**

## Deployment with nginx.
    We will run the application using uWSGI server and will be using nginx as a reverse proxy for serving the requests.
    We will use supervisor to manage the uWSGI server. The configuration for which can be found in the supervisord.conf
    You will need to download and install nginx on the box.
    Currently added the following to the http server in the nginx server config

```
    server {
        listen       80;
        server_name  _;

        location / { try_files $uri @app;}
        location @app {
            include uwsgi_params;
            uwsgi_pass unix:/tmp/uwsgi.sock;
        }

        }
```


    Have followed the following articles in figuring out the flask app deployment using nginx.
    [Digital Ocean: How to deploy flask applications using uwsgi behind nginx on centos](https://www.digitalocean.com/community/articles/how-to-deploy-flask-web-applications-using-uwsgi-behind-nginx-on-centos-6-4)
    [Deploying Flask with nginx, uWSGI and Supervisor](http://flaviusim.com/blog/Deploying-Flask-with-nginx-uWSGI-and-Supervisor/)


### Use the following make targets to control the project.
```
* $ make start : to start the app
* $ make stop : to stop the app.
* $ make reload : to reload new configurations [NOTE: This does not reload nginx]
* $ make status : to check the status of the running app.
* $ make clean : to delete pyc files (and pylint and test artifacts once added)
* $ make clobber: delete the virtual environment.
```

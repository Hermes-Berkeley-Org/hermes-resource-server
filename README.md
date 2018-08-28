# Hermes

To setup:

    pip3 install virtualenv
    virtualenv -p python3 venv
    source venv/bin/activate

    pip3 install -r requirements.txt

    chmod +x deploy/*
    source deploy/setup-env

    brew install heroku/brew/heroku
    heroku login
    heroku git:remote -a cal-hermes

To run locally:

    flask run --port=3000


**OK Bypass**: If you don't want to deal with OK auth in the application, make sure you set OK_MODE = bypass in setup-env.sh and you will operate as Sumukh in the application without having to login

**To access the DB**: Go to Heroku, Resources and click on MLab

**If you're getting weird errors on importing stuff**:

    rm -rf venv
    virtualenv -p python3 venv
    source venv/bin/activate
    pip3 install -r requirements.txt

**If you push with new environment variables**:

Make sure to also make changes in deploy/heroku_env, then run:

    heroku config:push --file deploy/heroku_env --overwrite

**Google Auth**:

Download the client_secret.json file from the Drive and put it in a directory called "keys"

**Other Keys**

Download all files in the "envs" folder from the Drive and put them in the deploy directory

## Docker Support

```
docker build -t hermes:latest .
docker run -p 3000:3000 --name hermes --env-file deploy/docker-env hermes:latest
```

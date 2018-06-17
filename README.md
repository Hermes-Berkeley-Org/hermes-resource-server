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

Once you set up your OK server (see https://github.com/Cal-CS-61A-Staff/ok), in order to test on Heroku:

    If you're running OK locally, make sure you ngrok it and set is an environment variable in setup-env.sh

    heroku config:set OK_SERVER=<your server, could be ngrok>


**OK Bypass**: If you don't want to deal with OK auth in the application, make sure you set OK_MODE = bypass in setup-env.sh and you will operate as Sumukh in the application without having to login

**To access the DB**: Go to Heroku, Resources and click on MLab

**If you're getting weird errors on importing stuff**:

    rm -rf venv
    virtualenv -p python3 venv
    source venv/bin/activate
    pip3 install -r requirements.txt

**Additional steps to install selenium**:

Go to https://sites.google.com/a/chromium.org/chromedriver/downloads and download the chromedriver. Move the chromedriver executable file into a good location on your computer and run:

    export PATH=$PATH:folder/with/chromedriver

**If you push with new environment variables**:

Make sure to also make changes in deploy/heroku_env, then run:

    heroku config:push --file deploy/heroku_env --overwrite

**Google Auth**:

Download the client_secret.json file from the Drive and put it in a directory called "keys"

**Other Keys**

Download all files in the "envs" folder from the Drive and put them in the deploy directory

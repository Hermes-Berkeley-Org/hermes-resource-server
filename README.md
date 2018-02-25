# hermes

To setup:

    pip install virtualenv
    virtualenv venv
    source venv/bin/activate

    pip install -r requirements.txt

    chmod +x deploy/*
    deploy/setup-env

    brew install heroku/brew/heroku
    heroku git:remote -a cal-hermes

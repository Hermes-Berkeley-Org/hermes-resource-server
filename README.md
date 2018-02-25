# hermes

To setup:

    pip install virtualenv
    virtualenv venv
    source venv/bin/activate

    pip install -r requirements.txt

    chmod +x deploy/*
    deploy/setup-env

    brew install heroku/brew/heroku
    heroku login
    heroku git:remote -a cal-hermes

To run locally:

    flask run

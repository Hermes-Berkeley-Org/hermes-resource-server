import google.oauth2.credentials
import google_auth_oauthlib.flow


CLIENT_SECRET_FILE = 'keys/client_secret.json'

def get_authorization_url(redirect_uri):
    flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
        'client_secret.json',
        scope=['https://www.googleapis.com/auth/youtube.force-ssl'])
    flow.redirect_uri = redirect_uri

    return flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true'
    )

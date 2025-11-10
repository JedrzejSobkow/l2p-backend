# app/infrastructure/google_oauth.py

from httpx_oauth.clients.google import GoogleOAuth2
from config.settings import settings


# Initialize Google OAuth2 client
# The GoogleOAuth2 client includes default scopes for openid, email, and profile
google_oauth_client = GoogleOAuth2(
    client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
    client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
)

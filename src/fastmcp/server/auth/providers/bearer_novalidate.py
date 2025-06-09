"""
BearerNoValidateAuthProvider: Accepts any non-empty Bearer token, no validation.
"""

from mcp.server.auth.provider import AccessToken

from fastmcp.server.auth.auth import (
    ClientRegistrationOptions,
    OAuthProvider,
    RevocationOptions,
)


class BearerNoValidateAuthProvider(OAuthProvider):
    """
    Accepts any non-empty Bearer token as valid. No signature, issuer, audience, or expiration validation.
    Intended for development or trusted environments only.
    """

    def __init__(
        self,
        required_scopes: list[str] | None = None,
    ):
        super().__init__(
            issuer_url="https://cashmere.io",
            client_registration_options=ClientRegistrationOptions(enabled=False),
            revocation_options=RevocationOptions(enabled=False),
            required_scopes=required_scopes,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        """
        Accepts any non-empty token and returns a minimal AccessToken. Returns None if token is empty.
        """
        if not token or not token.strip():
            return None
        return AccessToken(
            token=token,
            client_id="anonymous",
            scopes=[],
            expires_at=None,
        )

    # --- Unused OAuth server methods ---
    async def get_client(self, client_id: str):
        raise NotImplementedError("Client management not supported")

    async def register_client(self, client_info):
        raise NotImplementedError("Client registration not supported")

    async def authorize(self, client, params):
        raise NotImplementedError("Authorization flow not supported")

    async def load_authorization_code(self, client, authorization_code):
        raise NotImplementedError("Authorization code flow not supported")

    async def exchange_authorization_code(self, client, authorization_code):
        raise NotImplementedError("Authorization code exchange not supported")

    async def load_refresh_token(self, client, refresh_token):
        raise NotImplementedError("Refresh token flow not supported")

    async def exchange_refresh_token(self, client, refresh_token, scopes):
        raise NotImplementedError("Refresh token exchange not supported")

    async def revoke_token(self, token):
        raise NotImplementedError("Token revocation not supported")

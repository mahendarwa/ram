import os
import time

import requests
from azure.core.credentials import AccessToken
from azure.identity import DefaultAzureCredential
from msal import ConfidentialClientApplication


class ClientAssertionCredential(object):
    def __init__(self):
        azure_client_id = os.getenv("AZURE_CLIENT_ID", "")
        azure_tenant_id = os.getenv("AZURE_TENANT_ID", "")
        azure_authority_host = os.getenv("AZURE_AUTHORITY_HOST", "")
        azure_federated_token_file = os.getenv("AZURE_FEDERATED_TOKEN_FILE", "")

        # read the projected service account token file
        f = open(azure_federated_token_file, "rb")
        # create a confidential client application
        self.app = ConfidentialClientApplication(
            azure_client_id,
            client_credential={"client_assertion": f.read().decode("utf-8")},
            authority="{}{}".format(azure_authority_host, azure_tenant_id),
        )

    def get_token(self, *scopes, **kwargs):
        # get the token using the application
        token = self.app.acquire_token_for_client(scopes)
        if "error" in token:
            raise Exception(token["error_description"])
        expires_on = time.time() + token["expires_in"]
        # return an access token with the token string and expiration time
        return AccessToken(token["access_token"], int(expires_on))

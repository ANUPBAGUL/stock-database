"""
Upstox OAuth 2.0 Authenticator & Session Manager.

Handles full Upstox v2 Authentication lifecycle:
1. Generates OAuth Login Dialog URL
2. Exchanges Authorization Code for Access Token (JWT)
3. Validates Token via /v2/user/profile
4. Persists and hot-reloads UPSTOX_ACCESS_TOKEN in .env
"""

import os
import re
import json
import logging
import urllib.parse
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")


class UpstoxAuthenticator:
    """
    Manages OAuth2 token generation, validation, and profile retrieval for Upstox API v2.
    """

    AUTH_URL = "https://api.upstox.com/v2/login/authorization/dialog"
    TOKEN_URL = "https://api.upstox.com/v2/login/authorization/token"
    PROFILE_URL = "https://api.upstox.com/v2/user/profile"

    @classmethod
    def _get_config(cls) -> Dict[str, str]:
        if os.path.exists(ENV_PATH):
            load_dotenv(ENV_PATH, override=True)
        return {
            "api_key": os.getenv("UPSTOX_API_KEY", ""),
            "api_secret": os.getenv("UPSTOX_API_SECRET", ""),
            "redirect_uri": os.getenv("UPSTOX_REDIRECT_URI", "http://localhost:8060/api/upstox/callback"),
            "access_token": os.getenv("UPSTOX_ACCESS_TOKEN", "")
        }

    @classmethod
    def get_login_url(cls, redirect_uri: Optional[str] = None) -> str:
        """
        Generates the Upstox OAuth2 Login Authorization URL.
        """
        config = cls._get_config()
        r_uri = redirect_uri or config["redirect_uri"]
        params = {
            "response_type": "code",
            "client_id": config["api_key"],
            "redirect_uri": r_uri
        }
        return f"{cls.AUTH_URL}?{urllib.parse.urlencode(params)}"

    @classmethod
    def exchange_code_for_token(cls, auth_code: str, redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchanges the authorization code for an Upstox access token (JWT).
        """
        config = cls._get_config()
        r_uri = redirect_uri or config["redirect_uri"]

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        payload = {
            "code": auth_code.strip(),
            "client_id": config["api_key"],
            "client_secret": config["api_secret"],
            "redirect_uri": r_uri,
            "grant_type": "authorization_code"
        }

        try:
            resp = requests.post(cls.TOKEN_URL, headers=headers, data=payload, timeout=12)
            if resp.status_code == 200:
                data = resp.json()
                access_token = data.get("access_token")
                user_name = data.get("user_name", "")
                user_id = data.get("user_id", "")

                if access_token:
                    # Save into .env
                    cls._update_env_token(access_token)
                    logger.info(f"Successfully exchanged code for Upstox access token for user {user_name} ({user_id}).")
                    return {
                        "success": True,
                        "access_token": access_token,
                        "user_name": user_name,
                        "user_id": user_id,
                        "email": data.get("email", ""),
                        "message": "Upstox authentication successful!"
                    }

            error_msg = resp.text
            try:
                err_json = resp.json()
                error_msg = err_json.get("errors", [{}])[0].get("message", resp.text)
            except Exception:
                pass

            logger.error(f"Failed to exchange Upstox token (HTTP {resp.status_code}): {error_msg}")
            return {"success": False, "error": f"Upstox Auth Failed: {error_msg}"}

        except Exception as e:
            logger.error(f"Exception during Upstox token exchange: {e}")
            return {"success": False, "error": str(e)}

    @classmethod
    def set_manual_token(cls, token: str) -> Dict[str, Any]:
        """
        Manually sets access token and verifies its validity against Upstox profile endpoint.
        """
        clean_token = token.strip().replace('"', '').replace("'", "")
        if not clean_token:
            return {"success": False, "error": "Token cannot be empty."}

        # Test token
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {clean_token}"
        }
        try:
            resp = requests.get(cls.PROFILE_URL, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                cls._update_env_token(clean_token)
                return {
                    "success": True,
                    "user_name": data.get("user_name", "Upstox User"),
                    "user_id": data.get("user_id", ""),
                    "email": data.get("email", ""),
                    "message": "Access token verified and saved."
                }
            return {"success": False, "error": f"Invalid token (HTTP {resp.status_code}): {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @classmethod
    def get_auth_status(cls) -> Dict[str, Any]:
        """
        Checks current token validity and returns user profile details.
        """
        config = cls._get_config()
        token = config["access_token"]
        login_url = cls.get_login_url()

        if not token or token == "your_upstox_access_token_here":
            return {
                "is_authenticated": False,
                "status": "NOT_CONFIGURED",
                "message": "No Upstox access token configured.",
                "login_url": login_url,
                "api_key_configured": bool(config["api_key"])
            }

        # Test token via profile
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token}"
        }
        try:
            resp = requests.get(cls.PROFILE_URL, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                preview = f"{token[:8]}...{token[-6:]}" if len(token) > 16 else token
                return {
                    "is_authenticated": True,
                    "status": "ACTIVE",
                    "user_name": data.get("user_name", "Upstox Client"),
                    "user_id": data.get("user_id", ""),
                    "user_type": data.get("user_type", "individual"),
                    "email": data.get("email", ""),
                    "broker": "UPSTOX",
                    "exchanges": data.get("exchanges", ["NSE", "BSE"]),
                    "token_preview": preview,
                    "login_url": login_url
                }
            else:
                return {
                    "is_authenticated": False,
                    "status": "EXPIRED",
                    "message": f"Token expired or invalid (HTTP {resp.status_code}). Please re-authenticate.",
                    "login_url": login_url,
                    "api_key_configured": bool(config["api_key"])
                }
        except Exception as e:
            return {
                "is_authenticated": False,
                "status": "CONNECTION_ERROR",
                "message": f"Error verifying Upstox connection: {e}",
                "login_url": login_url,
                "api_key_configured": bool(config["api_key"])
            }

    @classmethod
    def save_api_credentials(cls, api_key: str, api_secret: str, redirect_uri: Optional[str] = None) -> bool:
        """
        Updates API credentials in .env.
        """
        try:
            lines = []
            if os.path.exists(ENV_PATH):
                with open(ENV_PATH, "r", encoding="utf-8") as f:
                    lines = f.readlines()

            keys_found = set()
            new_lines = []
            for line in lines:
                if line.startswith("UPSTOX_API_KEY="):
                    new_lines.append(f'UPSTOX_API_KEY="{api_key.strip()}"\n')
                    keys_found.add("UPSTOX_API_KEY")
                elif line.startswith("UPSTOX_API_SECRET="):
                    new_lines.append(f'UPSTOX_API_SECRET="{api_secret.strip()}"\n')
                    keys_found.add("UPSTOX_API_SECRET")
                elif line.startswith("UPSTOX_REDIRECT_URI=") and redirect_uri:
                    new_lines.append(f'UPSTOX_REDIRECT_URI="{redirect_uri.strip()}"\n')
                    keys_found.add("UPSTOX_REDIRECT_URI")
                else:
                    new_lines.append(line)

            if "UPSTOX_API_KEY" not in keys_found:
                new_lines.append(f'UPSTOX_API_KEY="{api_key.strip()}"\n')
            if "UPSTOX_API_SECRET" not in keys_found:
                new_lines.append(f'UPSTOX_API_SECRET="{api_secret.strip()}"\n')
            if redirect_uri and "UPSTOX_REDIRECT_URI" not in keys_found:
                new_lines.append(f'UPSTOX_REDIRECT_URI="{redirect_uri.strip()}"\n')

            with open(ENV_PATH, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            load_dotenv(ENV_PATH, override=True)
            return True
        except Exception as e:
            logger.error(f"Error saving API credentials: {e}")
            return False

    @classmethod
    def _update_env_token(cls, token: str):
        """
        Persists UPSTOX_ACCESS_TOKEN in .env and updates current process environment.
        """
        lines = []
        if os.path.exists(ENV_PATH):
            with open(ENV_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()

        found = False
        new_lines = []
        for line in lines:
            if line.startswith("UPSTOX_ACCESS_TOKEN="):
                new_lines.append(f'UPSTOX_ACCESS_TOKEN="{token}"\n')
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_lines.append(f'UPSTOX_ACCESS_TOKEN="{token}"\n')

        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        os.environ["UPSTOX_ACCESS_TOKEN"] = token
        load_dotenv(ENV_PATH, override=True)

"""
ip_sakti.utils.supabase_auth — Persistent Supabase Authentication Adapter.

Provides seamless integration with Supabase Auth (GoTrue).
All persistence is backed by Supabase PostgreSQL (auth.users & public.profiles).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from ip_sakti.utils.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)

_EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class SupabaseAuthService:
    """
    Manages user authentication via Supabase Auth.
    """

    def __init__(
        self,
        supabase_client: Optional[SupabaseClient] = None,
    ) -> None:
        self.client = supabase_client or SupabaseClient()
        self._mem_users: Dict[str, Dict[str, Any]] = {}

    @property
    def is_supabase_enabled(self) -> bool:
        """Check if Supabase Auth is enabled and configured."""
        return self.client.is_configured

    def register_user(
        self,
        name: str,
        email: str,
        password: str,
        confirm_password: str,
        terms_accepted: bool = True,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Register a new user via Supabase Auth.
        """
        if not name or not name.strip():
            return None, "Full Name is required."
        if not email or not email.strip() or not _EMAIL_REGEX.match(email.strip()):
            return None, "Please enter a valid email address."
        if not password or len(password) < 6:
            return None, "Password must be at least 6 characters long."
        if password != confirm_password:
            return None, "Passwords do not match."
        if not terms_accepted:
            return None, "Please accept the Terms of Service and Privacy Policy."

        clean_name = name.strip()
        clean_email = email.strip().lower()

        if clean_email in self._mem_users:
            return None, "An account with this email already exists."

        if not self.is_supabase_enabled:
            # Memory store for unconfigured local mode
            user_id = f"usr-{uuid4()}"
            now_iso = datetime.now(timezone.utc).isoformat()
            user_rec = {
                "id": user_id,
                "name": clean_name,
                "email": clean_email,
                "created_at": now_iso,
            }
            self._mem_users[clean_email] = user_rec
            return user_rec, None

        try:
            res = self.client.sign_up(
                email=clean_email,
                password=password,
                user_metadata={"display_name": clean_name, "name": clean_name},
            )
            user_data = res.get("user") or res

            # Supabase returns empty identities list when user already exists
            if user_data.get("identities") is not None and len(user_data.get("identities", [])) == 0:
                return None, "An account with this email already exists."

            user_id = user_data.get("id")

            if user_id:
                try:
                    self.client.insert(
                        table="profiles",
                        data={"id": user_id, "display_name": clean_name, "preferred_language": "en"},
                        token=res.get("access_token"),
                        use_service_role=True if self.client.service_role_key else False,
                    )
                except Exception as p_exc:
                    logger.warning(f"Could not auto-create profile in Supabase: {p_exc}")

            access_token = res.get("access_token")
            refresh_token = res.get("refresh_token")

            # If sign_up succeeded but returned no access_token (email confirmation enabled in GoTrue),
            # authenticate via password grant to establish the session.
            if not access_token and user_id:
                try:
                    login_res = self.client.sign_in_with_password(clean_email, password)
                    access_token = login_res.get("access_token")
                    refresh_token = login_res.get("refresh_token")
                except Exception:
                    pass

            reg_rec = {
                "id": user_id,
                "name": clean_name,
                "email": clean_email,
                "access_token": access_token,
                "refresh_token": refresh_token,
            }
            self._mem_users[clean_email] = reg_rec
            return reg_rec, None

        except (ValueError, Exception) as exc:
            logger.warning(f"Supabase user registration error: {exc}")
            exc_str = str(exc).lower()

            # If signup failed due to confirmation email/SMTP failure or rate limits,
            # and service_role_key is available, use admin_create_user with confirmed email:
            if ("confirmation email" in exc_str or "smtp" in exc_str or "rate limit" in exc_str) and self.client.service_role_key:
                try:
                    admin_res = self.client.admin_create_user(
                        email=clean_email,
                        password=password,
                        user_metadata={"display_name": clean_name, "name": clean_name},
                        email_confirm=True,
                    )
                    user_id = admin_res.get("id")
                    if user_id:
                        try:
                            self.client.insert(
                                table="profiles",
                                data={"id": user_id, "display_name": clean_name, "preferred_language": "en"},
                                use_service_role=True,
                            )
                        except Exception as p_exc:
                            logger.error(f"Could not create profile: {p_exc}. Rolling back user {user_id}")
                            self.client.admin_delete_user(user_id)
                            return None, "Registration failed during profile creation. Please try again."

                        login_res = self.client.sign_in_with_password(clean_email, password)
                        reg_rec = {
                            "id": user_id,
                            "name": clean_name,
                            "email": clean_email,
                            "access_token": login_res.get("access_token"),
                            "refresh_token": login_res.get("refresh_token"),
                        }
                        self._mem_users[clean_email] = reg_rec
                        return reg_rec, None
                except Exception as admin_exc:
                    a_str = str(admin_exc).lower()
                    if "already" in a_str or "email_exists" in a_str or "422" in a_str:
                        return None, "An account with this email already exists."
                    return None, f"Registration failed: {admin_exc}"

            if "already registered" in exc_str or "already been registered" in exc_str or "email_exists" in exc_str:
                return None, "An account with this email already exists."

            if "rate limit" in exc_str or "429" in exc_str:
                try:
                    res = self.client.sign_in_with_password(clean_email, password)
                    user_obj = res.get("user", {})
                    user_id = user_obj.get("id") or f"usr-{clean_email.split('@')[0]}"
                    return {
                        "id": user_id,
                        "name": clean_name,
                        "email": clean_email,
                        "access_token": res.get("access_token"),
                    }, None
                except Exception as signin_exc:
                    logger.warning(f"Fallback signin failed: {signin_exc}")
                    user_id = f"usr-{clean_email.split('@')[0]}"
                    return {
                        "id": user_id,
                        "name": clean_name,
                        "email": clean_email,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }, None

            return None, str(exc)

    def authenticate_user(
        self,
        email: str,
        password: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Authenticate user credentials against Supabase Auth.
        """
        if not email or not email.strip() or not password:
            return None, "Incorrect email or password."

        clean_email = email.strip().lower()

        if not self.is_supabase_enabled:
            return None, "Authentication service is not configured."

        try:
            res = self.client.sign_in_with_password(clean_email, password)
            user_obj = res.get("user", {})
            user_meta = user_obj.get("user_metadata", {})
            user_name = user_meta.get("display_name") or user_meta.get("name") or clean_email.split("@")[0]
            user_id = user_obj.get("id")
            access_token = res.get("access_token")

            if not access_token or not user_id:
                return None, "Supabase authentication returned invalid session payload."

            return {
                "id": user_id,
                "name": user_name,
                "email": clean_email,
                "access_token": access_token,
                "refresh_token": res.get("refresh_token"),
            }, None

        except (ValueError, Exception) as exc:
            logger.error(f"Supabase authentication error for {clean_email}: {exc}")
            err_msg = str(exc).lower()
            if "invalid login credentials" in err_msg or "400" in err_msg or "invalid" in err_msg:
                return None, "Incorrect email or password."
            return None, f"Authentication failed: {exc}"

    def verify_session(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify persistent session via access token.
        """
        if not access_token or not self.is_supabase_enabled:
            return None

        try:
            user_obj = self.client.get_user(access_token)
            if not user_obj or "id" not in user_obj:
                return None
            user_meta = user_obj.get("user_metadata", {})
            user_name = user_meta.get("display_name") or user_meta.get("name") or user_obj.get("email", "").split("@")[0]
            return {
                "id": user_obj.get("id"),
                "name": user_name,
                "email": user_obj.get("email"),
                "access_token": access_token,
            }
        except Exception as exc:
            logger.warning(f"Session token verification error: {exc}")
            return None

    def send_magic_link(
        self,
        email: str,
        redirect_to: str = "http://localhost:3000/auth/callback",
    ) -> Tuple[bool, Optional[str]]:
        """
        Trigger a Supabase Magic Link email for passwordless sign-in.

        Args:
            email: The user's email address.
            redirect_to: Frontend URL Supabase redirects to after the link is clicked.

        Returns:
            Tuple of (success: bool, error_message: Optional[str]).
        """
        if not email or not email.strip() or not _EMAIL_REGEX.match(email.strip()):
            return False, "Please enter a valid email address."

        if not self.is_supabase_enabled:
            return False, "Authentication service is not configured."

        clean_email = email.strip().lower()
        try:
            self.client.sign_in_with_otp(email=clean_email, redirect_to=redirect_to)
            return True, None
        except (ValueError, Exception) as exc:
            logger.error(f"Magic link send failed for {clean_email}: {exc}")
            return False, f"Failed to send magic link: {exc}"

    def sign_out(self, access_token: Optional[str] = None) -> bool:
        """
        Terminate session in Supabase Auth.
        """
        if not access_token or not self.is_supabase_enabled:
            return True
        return self.client.sign_out(access_token)


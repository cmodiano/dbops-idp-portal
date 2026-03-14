"""
Story 31.8: Service de notification multi-destinations (email, Teams, page).

Ne pas hériter de BaseAdapter — ce n'est pas une plateforme d'exécution.
Conforme au pattern services/ (Story 27.9).
"""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from django.conf import settings
from django.core.mail import EmailMessage

logger = structlog.get_logger(__name__)

# Keys whose values must be masked in notifications (Story 58.2)
_SENSITIVE_PARAM_KEYS = frozenset(
    k.lower() for k in ("password", "token", "secret", "api_key", "apikey")
)
_MAX_PARAM_VALUE_LEN = 64

# NOTIF-MED-01: Module-level constants extracted to eliminate triple duplication
# in notify_execution_event(). Previously defined inline 3× (L267-272, L333-338, L353-357).
_EVENT_LABELS: dict[str, str] = {
    "on_success": "Succès",
    "on_failure": "Échec",
    "on_approval_required": "Approbation requise",
}
_EVENT_COLORS: dict[str, str] = {
    "on_success": "00FF00",
    "on_failure": "FF0000",
    "on_approval_required": "FFA500",
}
_PAGE_EVENT_LABELS: dict[str, str] = {
    "on_success": "a réussi",
    "on_failure": "a échoué",
    "on_approval_required": "attend une approbation",
}


def _format_params_for_notification(execution: Any) -> str:
    """Story 58.2: Formate parameters et targets pour inclusion dans notifications on_approval_required."""
    parts = []
    params = execution.get_parameters() if hasattr(execution, "get_parameters") else getattr(execution, "parameters", None)
    if params is not None:
        if isinstance(params, dict):
            safe_pairs = []
            for k, v in params.items():
                key_lower = str(k).lower()
                if key_lower in _SENSITIVE_PARAM_KEYS:
                    safe_pairs.append(f"{k}=***")
                else:
                    if isinstance(v, (dict, list)):
                        raw = f"[{type(v).__name__}]"
                    else:
                        raw = str(v) if v is not None else ""
                        if len(raw) > _MAX_PARAM_VALUE_LEN:
                            raw = raw[:_MAX_PARAM_VALUE_LEN] + "..."
                    safe_pairs.append(f"{k}={raw}")
            if safe_pairs:
                parts.append(f"Paramètres: {', '.join(safe_pairs)}")
        else:
            # Non-dict (list, string, etc.): safe summary only
            tname = type(params).__name__
            length = len(params) if hasattr(params, "__len__") else "?"
            parts.append(f"Paramètres: [{tname}, len={length}]")
    try:
        targets = list(execution.targets.all())
        if targets:
            target_names = ", ".join(t.target_name or t.target_id for t in targets)
            parts.append(f"Targets: {target_names}")
    except Exception as e:  # noqa: BLE001 — best-effort: target access must not break notification
        logger.warning(
            "notification_target_access_failed",
            error_type=type(e).__name__,
            error=str(e),
        )
    return " | ".join(parts) if parts else ""


class NotificationService:
    """Service de notification multi-destinations (email, Teams, page)."""

    def __init__(self, **config: Any) -> None:
        self.config = config

    def send_email(
        self,
        recipient_email: str,
        subject: str,
        body: str,
        cc: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Envoie un email via django.core.mail.EmailMessage.

        Args:
            cc: Adresses en copie, sous forme de chaîne séparée par virgule
                (ex. ``"admin@company.com,team@company.com"``). None ou chaîne
                vide → aucun destinataire CC.
        """
        try:
            cc_list = [addr.strip() for addr in cc.split(',') if addr.strip()] if cc else []
            EmailMessage(
                subject=subject,
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient_email],
                cc=cc_list,
            ).send()
            # Log only the domain part to avoid PII in structured logs
            _domain = recipient_email.split("@")[-1] if "@" in recipient_email else "?"
            logger.info(
                "notification_sent",
                destination_type="email",
                recipient_domain=_domain,
                has_cc=bool(cc_list),
                correlation_id=correlation_id,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort-non-critical: email notification failure must not break caller
            logger.error(
                "notification_failed",
                destination_type="email",
                error=type(exc).__name__,
                correlation_id=correlation_id,
            )

    def send_teams(
        self,
        webhook_url: str,
        message: str,
        title: str | None = None,
        color: str = "FF0000",
        correlation_id: str | None = None,
    ) -> None:
        """Envoie un message vers un canal Teams via webhook (MessageCard)."""
        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": title or message[:80],
            "sections": [{"activityTitle": title, "activityText": message}],
        }
        try:
            response = httpx.post(webhook_url, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(
                "notification_sent",
                destination_type="teams",
                correlation_id=correlation_id,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort-non-critical: Teams notification failure must not break caller
            logger.error(
                "notification_failed",
                destination_type="teams",
                error=type(exc).__name__,
                correlation_id=correlation_id,
            )

    def send_page_individual(
        self,
        user_id: str,
        user_name: str,
        message: str,
        action_name: str,
        execution_id: int,
        correlation_id: str | None = None,
    ) -> None:
        """Appelle l'API interne de page pour un individu."""
        api_url = getattr(settings, "PAGE_INDIVIDUAL_API_URL", "")
        if not api_url:
            logger.warning(
                "page_individual_not_configured",
                correlation_id=correlation_id,
            )
            return
        payload = {
            "user_id": user_id,
            "user_name": user_name,
            "message": message,
            "action_name": action_name,
            "execution_id": execution_id,
        }
        try:
            response = httpx.post(api_url, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(
                "notification_sent",
                destination_type="page_individual",
                user_id=user_id,
                correlation_id=correlation_id,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort-non-critical: page individual notification failure must not break caller
            logger.error(
                "notification_failed",
                destination_type="page_individual",
                error=type(exc).__name__,
                correlation_id=correlation_id,
            )

    def send_page_oncall(
        self,
        message: str,
        action_name: str,
        execution_id: int,
        level: str,
        correlation_id: str | None = None,
        api_url: str | None = None,
    ) -> None:
        """Appelle l'API interne de page on-call (agnostique). Epic 56."""
        effective_url = api_url or getattr(settings, "PAGE_ONCALL_API_URL", "")
        if not effective_url:
            logger.warning(
                "page_oncall_not_configured",
                correlation_id=correlation_id,
            )
            return
        payload = {
            "level": level,
            "message": message,
            "action_name": action_name,
            "execution_id": execution_id,
        }
        try:
            response = httpx.post(effective_url, json=payload, timeout=10.0)
            response.raise_for_status()
            logger.info(
                "notification_sent",
                destination_type="page_oncall",
                correlation_id=correlation_id,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort-non-critical: page on-call notification failure must not break caller
            logger.error(
                "notification_failed",
                destination_type="page_oncall",
                error=type(exc).__name__,
                correlation_id=correlation_id,
            )

    def notify(self, destination_type: str, **kwargs: Any) -> None:
        """Dispatch vers la méthode de destination appropriée."""
        dispatch: dict[str, Any] = {
            "email": self.send_email,
            "teams": self.send_teams,
            "page_individual": self.send_page_individual,
            "page_oncall": self.send_page_oncall,
        }
        handler = dispatch.get(destination_type)
        if handler is None:
            logger.error(
                "notification_unknown_destination",
                destination_type=destination_type,
            )
            return
        handler(**kwargs)

    # ------------------------------------------------------------------
    # NOTIF-MED-02: Helpers extraits de notify_execution_event() (Story 66.25)
    # ------------------------------------------------------------------

    def _get_event_label(self, event: str) -> tuple[str, str]:
        """Retourne (label, color) pour un event donné.

        Utilise les constantes module-level _EVENT_LABELS et _EVENT_COLORS.
        """
        label = _EVENT_LABELS.get(event, event.replace("_", " "))
        color = _EVENT_COLORS.get(event, "808080")
        return label, color

    def _get_page_event_label(self, event: str) -> str:
        """Retourne le libellé page (passé composé) pour un event donné.

        Utilise la constante module-level _PAGE_EVENT_LABELS.
        """
        return _PAGE_EVENT_LABELS.get(event, event.replace("_", " "))

    def _dispatch_email_channel(
        self,
        channel: dict,
        execution: Any,
        action: Any,
        env: str,
        event: str,
        event_label: str,
        correlation_id: str | None,
    ) -> None:
        """Dispatch le canal email vers send_email()."""
        recipient = channel.get("recipient", "requester")
        if recipient == "requester":
            recipient = getattr(execution.user, "email", "") or ""
        if not recipient:
            return
        if event == "on_approval_required":
            context_str = _format_params_for_notification(execution)
            body = (
                f"Approbation requise pour l'action '{action.name}' "
                f"dans l'environnement '{env}' (exécution {execution.id})."
                + (f"\n{context_str}" if context_str else "")
            )
        else:
            body = (
                f"Exécution {execution.id} pour l'action '{action.name}' "
                f"dans l'environnement '{env}' : {event.replace('_', ' ')}."
            )
        self.send_email(
            recipient_email=recipient,
            subject=f"[IDP Portal] {action.name} — {event_label}",
            body=body,
            correlation_id=correlation_id,
        )

    def _dispatch_teams_channel(
        self,
        channel: dict,
        execution: Any,
        action: Any,
        env: str,
        event: str,
        event_label: str,
        event_color: str,
        correlation_id: str | None,
    ) -> None:
        """Dispatch le canal Teams vers send_teams()."""
        webhook_url = channel.get("webhook_url_ref", "")
        # Vault resolution hors scope (v1 : URLs directes uniquement)
        if not webhook_url or webhook_url.startswith("vault:"):
            return
        if event == "on_approval_required":
            context_str = _format_params_for_notification(execution)
            message = (
                f"Action '{action.name}' [{env}] : approbation requise (exécution {execution.id})"
                + (f"\n{context_str}" if context_str else "")
            )
        else:
            message = (
                f"Action '{action.name}' [{env}] : "
                f"{event.replace('_', ' ')} (exécution {execution.id})"
            )
        self.send_teams(
            webhook_url=webhook_url,
            title=f"[IDP Portal] {action.name} — {event_label}",
            message=message,
            color=event_color,
            correlation_id=correlation_id,
        )

    def _dispatch_page_oncall_channel(
        self,
        channel: dict,
        execution: Any,
        action: Any,
        env: str,
        event: str,
        level: str,
        can_page: bool,
        correlation_id: str | None,
    ) -> None:
        """Dispatch le canal page on-call vers send_page_oncall() si can_page."""
        if not can_page:
            return
        api_url = channel.get("api_url", "")
        page_event_label = self._get_page_event_label(event)
        self.send_page_oncall(
            api_url=api_url,
            message=(
                f"Action critique '{action.name}' [{env}] "
                f"{page_event_label} (exécution {execution.id})"
            ),
            action_name=action.name,
            execution_id=execution.id,
            level=level,
            correlation_id=correlation_id,
        )

    def notify_execution_event(
        self,
        execution: Any,
        action: Any,
        event: str,  # "on_success" | "on_failure" | "on_approval_required" (Story 57.8)
        page_me: bool = False,
        page_me_user_id: str | None = None,
        page_me_user_name: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Point d'entrée principal — traite tous les canaux définis sur l'action.

        NOTIF-MED-02 (Story 66.25): Décomposé en helpers _dispatch_*_channel() et
        _get_event_label() / _get_page_event_label() pour réduire la complexité cyclomatique.
        """
        config = action.notification_config or {}
        channels = config.get("channels", [])
        page_individual_enabled = config.get("page_individual_enabled", False)

        # Calcul du niveau d'impact
        env = execution.environment
        impact_rules = action.impact_rules or {}
        env_rules = impact_rules.get(env, {})
        level = env_rules.get("level") or action.default_impact_level or "low"
        can_page = (env == "prod") and (level == "critical")

        event_label, event_color = self._get_event_label(event)

        # Dispatch canaux configurés sur l'action
        for channel in channels:
            if not channel.get("enabled", False):
                continue
            conditions = channel.get("conditions", [])
            if event not in conditions and "always" not in conditions:
                continue

            ch_type = channel.get("type")
            if ch_type == "email":
                self._dispatch_email_channel(channel, execution, action, env, event, event_label, correlation_id)
            elif ch_type == "teams":
                self._dispatch_teams_channel(channel, execution, action, env, event, event_label, event_color, correlation_id)
            elif ch_type == "page_oncall":
                self._dispatch_page_oncall_channel(channel, execution, action, env, event, level, can_page, correlation_id)

        # Page individuel — option à l'exécution
        if page_me and page_individual_enabled and can_page and page_me_user_id:
            page_me_event_label = self._get_page_event_label(event)
            self.send_page_individual(
                user_id=page_me_user_id,
                user_name=page_me_user_name or page_me_user_id,
                message=(
                    f"Action '{action.name}' [{env}] "
                    f"{page_me_event_label} (exécution {execution.id})"
                ),
                action_name=action.name,
                execution_id=execution.id,
                correlation_id=correlation_id,
            )

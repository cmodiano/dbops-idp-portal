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
from django.core.mail import send_mail

logger = structlog.get_logger(__name__)


def _format_params_for_notification(execution: Any) -> str:
    """Story 58.2: Formate parameters et targets pour inclusion dans notifications on_approval_required."""
    parts = []
    params = execution.get_parameters() if hasattr(execution, "get_parameters") else getattr(execution, "parameters", None)
    if params:
        params_str = ", ".join(f"{k}={v}" for k, v in params.items())
        parts.append(f"Paramètres: {params_str}")
    try:
        targets = list(execution.targets.all())
        if targets:
            target_names = ", ".join(t.target_name or t.target_id for t in targets)
            parts.append(f"Targets: {target_names}")
    except Exception:  # noqa: BLE001
        pass
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
        correlation_id: str | None = None,
    ) -> None:
        """Envoie un email via django.core.mail.send_mail()."""
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False,
            )
            # Log only the domain part to avoid PII in structured logs
            _domain = recipient_email.split("@")[-1] if "@" in recipient_email else "?"
            logger.info(
                "notification_sent",
                destination_type="email",
                recipient_domain=_domain,
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
        effective_url = (
            api_url
            or getattr(settings, "PAGE_ONCALL_API_URL", "")
            or getattr(settings, "PAGE_DBA_API_URL", "")
        )
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

    # Backward compatibility alias — Epic 56
    send_page_dba = send_page_oncall

    def notify(self, destination_type: str, **kwargs: Any) -> None:
        """Dispatch vers la méthode de destination appropriée."""
        dispatch: dict[str, Any] = {
            "email": self.send_email,
            "teams": self.send_teams,
            "page_individual": self.send_page_individual,
            "page_oncall": self.send_page_oncall,
            "page_dba": self.send_page_oncall,  # Backward compat alias — Epic 56
        }
        handler = dispatch.get(destination_type)
        if handler is None:
            logger.error(
                "notification_unknown_destination",
                destination_type=destination_type,
            )
            return
        handler(**kwargs)

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
        """Point d'entrée principal — traite tous les canaux définis sur l'action."""
        config = action.notification_config or {}
        channels = config.get("channels", [])
        page_individual_enabled = config.get("page_individual_enabled", False)

        # Calcul du niveau d'impact
        env = execution.environment
        impact_rules = action.impact_rules or {}
        env_rules = impact_rules.get(env, {})
        level = env_rules.get("level") or action.default_impact_level or "low"

        is_prod = env == "prod"
        is_critical = level == "critical"
        can_page = is_prod and is_critical

        # Story 57.8: Labels pour on_approval_required
        event_labels = {
            "on_success": "Succès",
            "on_failure": "Échec",
            "on_approval_required": "Approbation requise",
        }
        event_colors = {"on_success": "00FF00", "on_failure": "FF0000", "on_approval_required": "FFA500"}
        event_label = event_labels.get(event, event.replace("_", " "))
        event_color = event_colors.get(event, "808080")

        for channel in channels:
            if not channel.get("enabled", False):
                continue
            conditions = channel.get("conditions", [])
            if event not in conditions and "always" not in conditions:
                continue

            ch_type = channel.get("type")
            if ch_type == "email":
                recipient = channel.get("recipient", "requester")
                if recipient == "requester":
                    recipient = getattr(execution.user, "email", "") or ""
                if recipient:
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

            elif ch_type == "teams":
                webhook_url = channel.get("webhook_url_ref", "")
                # Vault resolution hors scope (v1 : URLs directes uniquement)
                if webhook_url and not webhook_url.startswith("vault:"):
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

            elif ch_type in ("page_oncall", "page_dba") and can_page:
                api_url = channel.get("api_url", "")
                page_event_labels = {
                    "on_success": "a réussi",
                    "on_failure": "a échoué",
                    "on_approval_required": "attend une approbation",
                }
                page_event_label = page_event_labels.get(event, event.replace("_", " "))
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

        # Page individuel — option à l'exécution
        if page_me and page_individual_enabled and can_page and page_me_user_id:
            page_event_labels = {
                "on_success": "a réussi",
                "on_failure": "a échoué",
                "on_approval_required": "attend une approbation",
            }
            page_me_event_label = page_event_labels.get(event, event.replace("_", " "))
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

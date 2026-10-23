import abc
import json
import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)


class BaseNotifier(abc.ABC):
    @abc.abstractmethod
    def send_alert(self, incident: Dict[str, Any]) -> bool:
        """Sends an incident alert."""
        pass


class ConsoleNotifier(BaseNotifier):
    """Outputs structured alerts to console/standard logging."""

    def send_alert(self, incident: Dict[str, Any]) -> bool:
        logger.warning(
            f"[ALERT CONSOLE] Incident {incident.get('incident_id')} | "
            f"Severity: {incident.get('severity')} | Check: {incident.get('check_name')} | "
            f"Category: {incident.get('rule_category')} | Message: {incident.get('details', {}).get('description')}"
        )
        return True


class FileNotifier(BaseNotifier):
    """Appends JSON-serialized incident alerts to a specified log file."""

    def __init__(self, file_path: str = "alerts.log"):
        self.file_path = file_path

    def send_alert(self, incident: Dict[str, Any]) -> bool:
        try:
            with open(self.file_path, "a") as f:
                f.write(json.dumps(incident) + "\n")
            return True
        except Exception as e:
            logger.error(f"Failed to write alert to file {self.file_path}: {e}")
            return False


class SlackNotifier(BaseNotifier):
    """Sends incident alerts to a Slack Webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url

    def send_alert(self, incident: Dict[str, Any]) -> bool:
        if not self.webhook_url:
            logger.info("Slack webhook URL not set; skipping webhook dispatch.")
            return False

        payload = {
            "text": f":warning: *Integration Monitor Alert [{incident.get('severity')}]*\n"
                    f"*Check:* `{incident.get('check_name')}`\n"
                    f"*Category:* `{incident.get('rule_category')}`\n"
                    f"*Incident ID:* `{incident.get('incident_id')}`\n"
                    f"*Details:* {incident.get('details', {}).get('description')}\n"
                    f"*Affected Count:* {len(incident.get('affected_record_ids', []))}"
        }
        try:
            resp = requests.post(self.webhook_url, json=payload, timeout=5.0)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Failed to dispatch Slack alert: {e}")
            return False


class PluggableNotifierManager:
    """Manages active notifiers and dispatches alerts across configured destinations."""

    def __init__(self, notifiers: Optional[list[BaseNotifier]] = None):
        self.notifiers = notifiers or [ConsoleNotifier()]

    def add_notifier(self, notifier: BaseNotifier) -> None:
        self.notifiers.append(notifier)

    def dispatch(self, incident: Dict[str, Any]) -> int:
        success_count = 0
        for n in self.notifiers:
            if n.send_alert(incident):
                success_count += 1
        return success_count

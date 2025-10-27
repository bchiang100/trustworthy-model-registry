"""License permissiveness metric."""

from __future__ import annotations

from acme_cli.metrics.base import Metric
from acme_cli.types import ModelContext
from acme_cli.utils import clamp

_PERMISSIVE = {
    "apache-2.0",
    "mit",
    "bsd-2-clause",
    "bsd-3-clause",
    "isc",
    "cc-by-4.0",
    "cc0-1.0",
}

_WEAK_COPYLEFT = {
    "lgpl-3.0",
    "mpl-2.0",
    "epl-2.0",
    "osl-3.0",
    "cc-by-sa-4.0",
}

_RESTRICTIVE = {
    "gpl-2.0",
    "gpl-3.0",
    "agpl-3.0",
    "cc-by-nc-4.0",
    "cc-by-nc-sa-4.0",
}


class LicenseMetric(Metric):
    name = "license"

    def compute(self, context: ModelContext) -> float:
        metadata = context.model_metadata
        if not metadata:
            return 0.0
        license_value = self._extract_license(metadata.card_data)
        if not license_value:
            return 0.0
        license_value = license_value.lower()
        if license_value in _PERMISSIVE:
            return 1.0
        if license_value in _WEAK_COPYLEFT:
            return 0.7
        if license_value in _RESTRICTIVE:
            return 0.2
        return clamp(0.4)

    @staticmethod
    def _extract_license(card_data: dict[str, object]) -> str | None:
        value = card_data.get("license")
        if isinstance(value, str):
            return value
        if isinstance(value, list) and value:
            head = value[0]
            if isinstance(head, str):
                return head
            if isinstance(head, dict):
                lic = head.get("id") or head.get("name")
                if isinstance(lic, str):
                    return lic
        if isinstance(value, dict):
            lic = value.get("id") or value.get("name")
            if isinstance(lic, str):
                return lic
        return None


__all__ = ["LicenseMetric"]

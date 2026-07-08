"""Comparacion de versiones semver simplificada."""
import re
from dataclasses import dataclass


_SEMVER_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")


@dataclass(frozen=True, order=True)
class Version:
    """Version semver comparable."""
    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, s: str) -> "Version | None":
        """Retorna None si el string no es un semver reconocible."""
        m = _SEMVER_RE.match(s.strip())
        if not m:
            return None
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

import json
import subprocess
import sys

DOMAIN_MODULES = [
    "fabric.inventory.domain.errors",
    "fabric.inventory.domain.events",
    "fabric.inventory.domain.order",
    "fabric.inventory.domain.picker",
    "fabric.inventory.domain.roll",
    "fabric.inventory.domain.values",
]


def test_domain_depends_only_on_stdlib() -> None:
    # A fresh interpreter, so modules imported by other tests do not hide a leak.
    script = (
        "import json, sys\n"
        "before = set(sys.modules)\n"
        f"for name in {DOMAIN_MODULES!r}: __import__(name)\n"
        "print(json.dumps(sorted(set(sys.modules) - before)))"
    )
    output = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True
    ).stdout
    loaded = json.loads(output)

    outsiders = [
        name
        for name in loaded
        if name.split(".")[0] not in sys.stdlib_module_names
        and not name.startswith("fabric.inventory.domain")
        and name not in {"fabric", "fabric.inventory"}
    ]
    assert outsiders == []

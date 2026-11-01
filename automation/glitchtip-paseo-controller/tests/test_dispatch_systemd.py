from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
SERVICE = ROOT / "systemd" / "ignite-glitchtip-paseo-controller-dispatch.service"
TIMER = ROOT / "systemd" / "ignite-glitchtip-paseo-controller-dispatch.timer"


class DispatchSystemdTests(unittest.TestCase):
    def test_dispatch_service_allows_bounded_commands_and_persists_only_controller_paths(
        self,
    ) -> None:
        service = SERVICE.read_text()

        self.assertIn("Type=oneshot", service)
        self.assertIn("TimeoutStartSec=5min", service)
        self.assertIn("Environment=XDG_STATE_HOME=%h/.local/state", service)
        self.assertIn("Environment=PASEO_HOME=%h/.paseo", service)
        self.assertIn("Environment=PASEO_HOST=127.0.0.1:6767", service)
        self.assertIn(
            "ReadWritePaths=%h/.local/state/ignite-glitchtip-paseo-controller "
            "%h/.local/state/ignite-glitchtip-paseo-controller-workspace %h/.paseo",
            service,
        )
        self.assertIn("dispatch --config config/controller.toml --once --enable-dispatch", service)
        self.assertIn("--config prd", service)
        self.assertNotIn("DOPPLER_TOKEN=", service)
        self.assertNotIn("Environment=GITHUB_AUTOMATION_TOKEN=", service)

    def test_dispatch_timer_is_persistent_and_targets_only_the_dispatch_service(self) -> None:
        timer = TIMER.read_text()

        self.assertIn("OnCalendar=*-*-* *:*:00", timer)
        self.assertNotIn("OnBootSec=", timer)
        self.assertNotIn("OnUnitActiveSec=", timer)
        self.assertIn("Persistent=true", timer)
        self.assertIn("Unit=ignite-glitchtip-paseo-controller-dispatch.service", timer)
        self.assertIn("WantedBy=timers.target", timer)


if __name__ == "__main__":
    unittest.main()

"""Validate integration file structure (no network access needed)."""

import ast
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
INTEGRATION = ROOT / "custom_components" / "skippo"


def _load_const():
    """Load const.py directly without going through the HA-dependent __init__.py."""
    spec = importlib.util.spec_from_file_location(
        "skippo_const", INTEGRATION / "const.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# manifest.json
# ---------------------------------------------------------------------------

class TestManifest:
    @pytest.fixture(scope="class")
    def manifest(self):
        return json.loads((INTEGRATION / "manifest.json").read_text())

    def test_required_fields(self, manifest):
        for field in ("domain", "name", "version", "config_flow", "iot_class", "codeowners"):
            assert field in manifest, f"manifest.json missing required field: {field!r}"

    def test_domain_matches_directory(self, manifest):
        assert manifest["domain"] == "skippo"

    def test_config_flow_enabled(self, manifest):
        assert manifest["config_flow"] is True

    def test_iot_class(self, manifest):
        assert manifest["iot_class"] == "cloud_polling"

    def test_version_semver(self, manifest):
        version = manifest["version"].lstrip("v")
        parts = version.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts), (
            f"version should be semver (vX.Y.Z or X.Y.Z), got: {manifest['version']!r}"
        )


# ---------------------------------------------------------------------------
# strings.json / translations
# ---------------------------------------------------------------------------

class TestStrings:
    @pytest.fixture(scope="class")
    def strings(self):
        return json.loads((INTEGRATION / "strings.json").read_text())

    def test_config_steps_present(self, strings):
        steps = strings.get("config", {}).get("step", {})
        assert "user" in steps, "strings.json missing config.step.user"
        assert "vessel" in steps, "strings.json missing config.step.vessel"

    def test_options_steps_present(self, strings):
        steps = strings.get("options", {}).get("step", {})
        assert "init" in steps, "strings.json missing options.step.init"
        assert "add_vessel" in steps, "strings.json missing options.step.add_vessel"
        assert "remove_vessel" in steps, "strings.json missing options.step.remove_vessel"

    def test_english_translation_exists(self):
        en = INTEGRATION / "translations" / "en.json"
        assert en.exists(), "translations/en.json is missing"
        data = json.loads(en.read_text())
        assert "config" in data or "options" in data, "en.json appears empty"

    def test_translations_valid_json(self):
        for path in (INTEGRATION / "translations").glob("*.json"):
            try:
                json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                pytest.fail(f"Invalid JSON in {path.name}: {exc}")


# ---------------------------------------------------------------------------
# icons.json
# ---------------------------------------------------------------------------

class TestIcons:
    @pytest.fixture(scope="class")
    def icons(self):
        path = INTEGRATION / "icons.json"
        assert path.exists(), "icons.json is missing"
        return json.loads(path.read_text())

    def test_valid_json(self):
        json.loads((INTEGRATION / "icons.json").read_text())

    def test_entity_section_present(self, icons):
        assert "entity" in icons, "icons.json missing top-level 'entity' key"

    def test_binary_sensor_icons_present(self, icons):
        bs = icons.get("entity", {}).get("binary_sensor", {})
        for key in ("online", "moving"):
            assert key in bs, f"icons.json missing binary_sensor.{key}"
            assert "default" in bs[key], f"icons.json binary_sensor.{key} missing 'default'"

    def test_sensor_icons_present(self, icons):
        sensors = icons.get("entity", {}).get("sensor", {})
        assert "speed" in sensors, "icons.json missing sensor.speed"

    def test_device_tracker_icons_present(self, icons):
        dt = icons.get("entity", {}).get("device_tracker", {})
        assert "vessel" in dt, "icons.json missing device_tracker.vessel"


# ---------------------------------------------------------------------------
# Python syntax
# ---------------------------------------------------------------------------

class TestPlatformFiles:
    def test_parallel_updates_defined(self):
        """Each entity platform must declare PARALLEL_UPDATES."""
        for platform in ("binary_sensor", "sensor", "device_tracker"):
            source = (INTEGRATION / f"{platform}.py").read_text()
            assert "PARALLEL_UPDATES" in source, (
                f"{platform}.py missing PARALLEL_UPDATES constant (Silver quality requirement)"
            )

    def test_diagnostics_platform_exists(self):
        assert (INTEGRATION / "diagnostics.py").exists(), (
            "diagnostics.py is missing (Gold quality requirement)"
        )

    def test_reconfigure_step_in_config_flow(self):
        source = (INTEGRATION / "config_flow.py").read_text()
        assert "async_step_reconfigure" in source, (
            "config_flow.py missing async_step_reconfigure (Platinum quality requirement)"
        )

    def test_py_typed_marker_exists(self):
        assert (INTEGRATION / "py.typed").exists(), (
            "py.typed marker missing (Platinum strict_typing requirement)"
        )


class TestPythonSyntax:
    @pytest.mark.parametrize("path", sorted(INTEGRATION.glob("*.py")))
    def test_syntax(self, path):
        source = path.read_text()
        try:
            ast.parse(source)
        except SyntaxError as exc:
            pytest.fail(f"Syntax error in {path.name}: {exc}")


# ---------------------------------------------------------------------------
# const.py — required constants
# ---------------------------------------------------------------------------

class TestConst:
    @pytest.fixture(scope="class")
    def const(self):
        return _load_const()

    def test_required_constants_present(self, const):
        required = [
            "DOMAIN",
            "API_BASE_URL",
            "SKIPPO_WEB_PLAN_URL",
            "BASIC_AUTH_FALLBACK",
            "SCAN_INTERVAL",
            "MANUFACTURER",
            "MODEL_AIS",
            "MODEL_USER",
            "TARGET_REGIONS",
            "DEFAULT_TARGET",
        ]
        for name in required:
            assert hasattr(const, name), f"const.py is missing: {name}"

    def test_basic_auth_fallback_is_valid_base64(self, const):
        import base64
        decoded = base64.b64decode(const.BASIC_AUTH_FALLBACK).decode()
        assert decoded.startswith("webClient:"), (
            f"BASIC_AUTH_FALLBACK does not decode to 'webClient:...': {decoded!r}"
        )

    def test_target_regions_contains_se(self, const):
        assert "SE" in const.TARGET_REGIONS

    def test_default_target_in_regions(self, const):
        assert const.DEFAULT_TARGET in const.TARGET_REGIONS

    def test_scan_interval_positive(self, const):
        assert const.SCAN_INTERVAL.total_seconds() > 0

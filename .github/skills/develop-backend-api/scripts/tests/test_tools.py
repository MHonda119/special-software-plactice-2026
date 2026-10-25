import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1]
MODULE_SPEC = importlib.util.spec_from_file_location(
    "api_inventory", SCRIPTS / "api_inventory.py"
)
inventory = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(inventory)

PROJECT_URLS = """
urlpatterns = [path("api/", include("core.urls"))]
"""
CORE_URLS = """
router = DefaultRouter()
router.register("widgets", WidgetViewSet, basename="widget")
router.register("tokens", TokenViewSet, basename="token")
urlpatterns = [path("health/", health), path("", include(router.urls))]
"""
VIEWS = """
@api_view(["GET"])
def health(request):
    pass

class WidgetViewSet(viewsets.ModelViewSet):
    queryset = Widget.objects.all()

    @action(detail=True, methods=["post"], url_path="refresh")
    def refresh(self, request, pk=None):
        pass

    @action(detail=False)
    def search(self, request):
        pass

    @action(
        detail=True, methods=["delete"],
        url_path=r"chunks/(?P<chunk_id>[^/.]+)",
    )
    def delete_chunk(self, request, pk=None, chunk_id=None):
        pass

class TokenViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Token.objects.filter(is_active=True)
"""
MODELS = """
class Widget(models.Model):
    name = models.CharField(max_length=100)

class Token(models.Model):
    uuid = models.UUIDField(primary_key=True)
"""


def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")


class RepositoryFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.views = self.root / "backend/core/views.py"
        self.urls = self.root / "backend/core/urls.py"
        write_file(self.root / "backend/lecture_system/urls.py", PROJECT_URLS)
        write_file(self.urls, CORE_URLS)
        write_file(self.views, VIEWS)
        write_file(self.root / "backend/core/models.py", MODELS)

    def write_documents(self):
        base, endpoints = inventory.collect_endpoints(self.root)
        directory = self.root / "docs/backend/api"
        self.index = directory / "README.md"
        self.details = directory / "widgets.md"
        write_file(
            self.index,
            "\n".join(
                f"| {method} | `{path}` | operation |"
                for method, path in sorted(endpoints)
            ),
        )
        write_file(
            self.details,
            "\n".join(
                f"| {method} | `{path}` | operation |"
                for method, path in sorted(endpoints - {("GET", base)})
            )
            + '\n```json\n{"ok": true}\n```\n[Index](README.md)\n',
        )
        return base, endpoints


class InventoryTests(RepositoryFixture):
    def test_crud_readonly_uuid_and_custom_actions(self):
        base, endpoints = inventory.collect_endpoints(self.root)
        self.assertEqual(base, "/api/")
        self.assertEqual(len(endpoints), 13)
        self.assertIn(("GET", "/api/tokens/{uuid}/"), endpoints)
        self.assertNotIn(("POST", "/api/tokens/"), endpoints)
        self.assertIn(("POST", "/api/widgets/{id}/refresh/"), endpoints)
        self.assertIn(("GET", "/api/widgets/search/"), endpoints)
        self.assertIn(("DELETE", "/api/widgets/{id}/chunks/{chunk_id}/"), endpoints)

    def test_explicit_lookup_and_http_method_restriction(self):
        write_file(
            self.views,
            VIEWS.replace(
                "queryset = Widget.objects.all()",
                "queryset = Widget.objects.all()\n"
                '    lookup_url_kwarg = "key"\n'
                '    http_method_names = ["get"]',
            ),
        )
        _, endpoints = inventory.collect_endpoints(self.root)
        self.assertIn(("GET", "/api/widgets/{key}/"), endpoints)
        self.assertNotIn(("POST", "/api/widgets/"), endpoints)
        self.assertNotIn(("POST", "/api/widgets/{key}/refresh/"), endpoints)

    def test_dynamic_prefix_is_not_silently_accepted(self):
        write_file(
            self.urls,
            CORE_URLS.replace('"widgets", WidgetViewSet', "PREFIX, WidgetViewSet"),
        )
        with self.assertRaisesRegex(inventory.InventoryError, "Dynamic"):
            inventory.collect_endpoints(self.root)

    def test_unknown_viewset_base_requires_manual_review(self):
        write_file(self.views, VIEWS.replace("viewsets.ModelViewSet", "CustomViewSet"))
        with self.assertRaisesRegex(inventory.InventoryError, "unsupported ViewSet"):
            inventory.collect_endpoints(self.root)

    def test_nested_include_requires_manual_review(self):
        write_file(
            self.urls,
            CORE_URLS.replace(
                'path("health/", health)',
                'path("extra/", include("extra.urls"))',
            ),
        )
        with self.assertRaisesRegex(inventory.InventoryError, "Nested URL"):
            inventory.collect_endpoints(self.root)

    def test_action_mapping_requires_manual_review(self):
        write_file(
            self.views,
            VIEWS.replace(
                "    def search(self, request):",
                "    @refresh.mapping.delete\n    def search(self, request):",
            ),
        )
        with self.assertRaisesRegex(inventory.InventoryError, "action.mapping"):
            inventory.collect_endpoints(self.root)

    def test_documents_and_json_and_links(self):
        base, endpoints = self.write_documents()
        self.assertEqual(
            inventory.check_documents(self.root, base, endpoints), (2, 1, 1)
        )

    def test_missing_index_operation_fails(self):
        base, endpoints = self.write_documents()
        self.index.write_text(
            self.index.read_text().replace("| GET | `/api/health/` | operation |", "")
        )
        with self.assertRaisesRegex(inventory.InventoryError, "index: missing"):
            inventory.check_documents(self.root, base, endpoints)

    def test_missing_individual_operation_fails(self):
        base, endpoints = self.write_documents()
        self.details.write_text(
            self.details.read_text().replace("| GET | `/api/health/` | operation |", "")
        )
        with self.assertRaisesRegex(
            inventory.InventoryError, "individual specifications: missing"
        ):
            inventory.check_documents(self.root, base, endpoints)

    def test_unimplemented_operation_fails(self):
        base, endpoints = self.write_documents()
        self.index.write_text(
            self.index.read_text() + "\n| GET | `/api/unknown/` | operation |"
        )
        with self.assertRaisesRegex(inventory.InventoryError, "unexpected=.*unknown"):
            inventory.check_documents(self.root, base, endpoints)

    def test_invalid_json_fails(self):
        base, endpoints = self.write_documents()
        self.details.write_text(
            self.details.read_text().replace('{"ok": true}', '{"ok":}')
        )
        with self.assertRaisesRegex(inventory.InventoryError, "invalid JSON"):
            inventory.check_documents(self.root, base, endpoints)

    def test_broken_link_fails(self):
        base, endpoints = self.write_documents()
        self.details.write_text(self.details.read_text() + "\n[Missing](missing.md)")
        with self.assertRaisesRegex(inventory.InventoryError, "broken local link"):
            inventory.check_documents(self.root, base, endpoints)

    def test_json_cli_from_another_directory(self):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "api_inventory.py"),
                "--root",
                str(self.root),
                "--json",
            ],
            cwd="/",
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(
            {"method": "GET", "path": "/api/tokens/{uuid}/"},
            json.loads(result.stdout),
        )

    def test_cli_missing_source_returns_nonzero(self):
        self.urls.unlink()
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "api_inventory.py"),
                "--root",
                str(self.root),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("ERROR:", result.stderr)


class RunnerTests(RepositoryFixture):
    def setUp(self):
        super().setUp()
        self.write_documents()
        self.runner = (
            self.root / ".github/skills/develop-backend-api/scripts/run_checks.sh"
        )
        self.runner.parent.mkdir(parents=True)
        shutil.copy2(SCRIPTS / "run_checks.sh", self.runner)
        shutil.copy2(
            SCRIPTS / "api_inventory.py",
            self.runner.parent / "api_inventory.py",
        )
        write_file(
            self.root / "scripts/test-backend.sh",
            'printf "%s\\n" test "$@" >> "$CALL_LOG"\n' 'exit "${TEST_EXIT_CODE:-0}"\n',
        )
        write_file(
            self.root / "scripts/lint-backend.sh",
            'printf "%s\\n" lint "$@" >> "$CALL_LOG"\n' 'exit "${LINT_EXIT_CODE:-0}"\n',
        )
        self.log = self.root / "calls.txt"

    def run_checks(self, *arguments, **environment):
        return subprocess.run(
            ["bash", str(self.runner), *arguments],
            cwd="/",
            env={**os.environ, "CALL_LOG": str(self.log), **environment},
            capture_output=True,
            text=True,
        )

    def test_default_docs_mode_does_not_invoke_containers(self):
        result = self.run_checks()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PASS:", result.stdout)
        self.assertFalse(self.log.exists())

    def test_labels_are_forwarded_without_shell_evaluation(self):
        result = self.run_checks(
            "test",
            "core.tests.test_agent_api",
            "label with spaces",
            "$(touch marker)",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.log.read_text().splitlines(),
            [
                "test",
                "core.tests.test_agent_api",
                "label with spaces",
                "$(touch marker)",
            ],
        )
        self.assertFalse((self.root / "marker").exists())

    def test_all_runs_lint_before_selected_tests(self):
        result = self.run_checks("all", "core.tests.test_agent_api")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.log.read_text().splitlines(),
            ["lint", "test", "core.tests.test_agent_api"],
        )

    def test_lint_failure_stops_all_and_preserves_exit_code(self):
        result = self.run_checks("all", LINT_EXIT_CODE="7")
        self.assertEqual(result.returncode, 7)
        self.assertEqual(self.log.read_text().splitlines(), ["lint"])

    def test_test_failure_preserves_exit_code(self):
        self.assertEqual(self.run_checks("test", TEST_EXIT_CODE="9").returncode, 9)

    def test_doc_failure_prevents_lint_and_tests(self):
        self.index.write_text("# Incomplete API index\n")
        result = self.run_checks("all")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.log.exists())

    def test_dry_run_has_no_command_side_effects(self):
        result = self.run_checks("--dry-run", "all", "core.tests.test_agent_api")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("test-backend.sh core.tests.test_agent_api", result.stdout)
        self.assertFalse(self.log.exists())

    def test_unknown_mode_and_inappropriate_arguments_fail(self):
        self.assertEqual(self.run_checks("unknown").returncode, 2)
        self.assertEqual(self.run_checks("docs", "core").returncode, 2)
        self.assertEqual(self.run_checks("lint", "--fix").returncode, 2)

    def test_help_succeeds_without_running_checks(self):
        result = self.run_checks("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("Usage:", result.stdout)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()

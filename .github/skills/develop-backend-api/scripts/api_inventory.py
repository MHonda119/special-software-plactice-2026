#!/usr/bin/env python3
"""Inspect this repository's literal DRF routes without importing Django."""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit


class InventoryError(ValueError):
    pass


def call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError) as error:
        raise InventoryError(
            "Dynamic route configuration needs manual review"
        ) from error


def parse_source(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def class_settings(view):
    return {
        target.id: assignment.value
        for assignment in view.body
        if isinstance(assignment, ast.Assign)
        for target in assignment.targets
        if isinstance(target, ast.Name)
    }


def lookup_name(view, models):
    settings = class_settings(view)
    for field in ("lookup_url_kwarg", "lookup_field"):
        if field in settings:
            value = literal(settings[field])
            if value and value != "pk":
                if not isinstance(value, str):
                    raise InventoryError(f"Invalid {field} in {view.name}")
                return value
    queryset = settings.get("queryset")
    if queryset is None:
        raise InventoryError(f"{view.name}: specify a literal lookup_field or queryset")
    model_names = [
        node.value.id
        for node in ast.walk(queryset)
        if isinstance(node, ast.Attribute)
        and node.attr == "objects"
        and isinstance(node.value, ast.Name)
    ]
    if len(model_names) != 1 or model_names[0] not in models:
        raise InventoryError(f"{view.name}: cannot resolve queryset model")
    for value in class_settings(models[model_names[0]]).values():
        if isinstance(value, ast.Call) and any(
            keyword.arg == "primary_key" and literal(keyword.value)
            for keyword in value.keywords
        ):
            return next(
                name
                for name, candidate in class_settings(models[model_names[0]]).items()
                if candidate is value
            )
    return "id"


def action_path(value):
    value = re.sub(
        r"\(\?P<(\w+)>[^)]+\)",
        lambda match: "{" + match.group(1) + "}",
        value,
    )
    if any(
        symbol in value
        for symbol in ("(", ")", "[", "]", "^", "$", "?", "*", "+", "|", "\\")
    ):
        raise InventoryError(f"Unsupported action URL expression: {value}")
    return value


def collect_endpoints(root):
    project = parse_source(root / "backend/lecture_system/urls.py")
    urls = parse_source(root / "backend/core/urls.py")
    views = parse_source(root / "backend/core/views.py")
    models_source = parse_source(root / "backend/core/models.py")
    models = {
        node.name: node for node in models_source.body if isinstance(node, ast.ClassDef)
    }
    definitions = {
        node.name: node
        for node in views.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }
    prefixes = [
        literal(node.args[0])
        for node in ast.walk(project)
        if isinstance(node, ast.Call)
        and call_name(node.func) == "path"
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Call)
        and call_name(node.args[1].func) == "include"
        and node.args[1].args
        and literal(node.args[1].args[0]) == "core.urls"
    ]
    if len(prefixes) != 1:
        raise InventoryError("Expected one literal include('core.urls')")
    base = "/" + prefixes[0]
    routers = {
        target.id
        for node in urls.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call)
        and call_name(node.value.func) == "DefaultRouter"
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    if len(routers) != 1:
        raise InventoryError("Expected one DefaultRouter in core/urls.py")
    endpoints = {("GET", base)}
    for node in urls.body:
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        registration = node.value
        if call_name(registration.func) != "register":
            continue
        if (
            not isinstance(registration.func, ast.Attribute)
            or call_name(registration.func.value) not in routers
        ):
            raise InventoryError("Unsupported router registration")
        prefix = literal(registration.args[0])
        if not isinstance(prefix, str) or not re.fullmatch(r"[\w/-]+", prefix):
            raise InventoryError("Router prefixes must be literal path segments")
        view = definitions.get(call_name(registration.args[1]))
        if not isinstance(view, ast.ClassDef):
            raise InventoryError(f"Cannot resolve ViewSet for {prefix}")
        bases = {call_name(parent) for parent in view.bases}
        if "ModelViewSet" in bases:
            collection_methods = ("GET", "POST")
            detail_methods = ("GET", "PUT", "PATCH", "DELETE")
        elif "ReadOnlyModelViewSet" in bases:
            collection_methods = detail_methods = ("GET",)
        else:
            raise InventoryError(
                f"{view.name}: unsupported ViewSet inheritance; "
                "inspect runtime routes"
            )
        collection = base + prefix.strip("/") + "/"
        detail = collection + "{" + lookup_name(view, models) + "}/"
        settings = class_settings(view)
        allowed = (
            {method.upper() for method in literal(settings["http_method_names"])}
            if "http_method_names" in settings
            else None
        )
        endpoints.update(
            (method, collection)
            for method in collection_methods
            if allowed is None or method in allowed
        )
        endpoints.update(
            (method, detail)
            for method in detail_methods
            if allowed is None or method in allowed
        )
        for method in view.body:
            if not isinstance(method, ast.FunctionDef):
                continue
            for decorator in method.decorator_list:
                if (
                    isinstance(decorator, ast.Attribute)
                    and isinstance(decorator.value, ast.Attribute)
                    and decorator.value.attr == "mapping"
                ):
                    raise InventoryError(
                        f"{view.name}: action.mapping " "needs runtime route review"
                    )
                if (
                    not isinstance(decorator, ast.Call)
                    or call_name(decorator.func) != "action"
                ):
                    continue
                kwargs = {
                    keyword.arg: literal(keyword.value)
                    for keyword in decorator.keywords
                }
                if "detail" not in kwargs:
                    raise InventoryError(
                        f"{view.name}.{method.name}: missing action detail"
                    )
                path = action_path(kwargs.get("url_path", method.name))
                route = (detail if kwargs["detail"] else collection) + path + "/"
                endpoints.update(
                    (verb.upper(), route)
                    for verb in kwargs.get("methods", ["get"])
                    if allowed is None or verb.upper() in allowed
                )
    patterns = next(
        (
            node.value
            for node in urls.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "urlpatterns"
                for target in node.targets
            )
        ),
        None,
    )
    if not isinstance(patterns, (ast.List, ast.Tuple)):
        raise InventoryError("urlpatterns must be a literal list or tuple")
    for pattern in patterns.elts:
        if not isinstance(pattern, ast.Call) or call_name(pattern.func) != "path":
            raise InventoryError("Only literal path() patterns are supported")
        route = base + literal(pattern.args[0])
        handler = pattern.args[1]
        if isinstance(handler, ast.Call) and call_name(handler.func) == "include":
            if (
                literal(pattern.args[0]) != ""
                or not isinstance(handler.args[0], ast.Attribute)
                or handler.args[0].attr != "urls"
                or call_name(handler.args[0].value) not in routers
            ):
                raise InventoryError("Nested URL includes need manual route review")
            continue
        function = definitions.get(call_name(handler))
        if not isinstance(function, ast.FunctionDef):
            raise InventoryError(f"Cannot resolve function view: {route}")
        decorator = next(
            (
                item
                for item in function.decorator_list
                if isinstance(item, ast.Call) and call_name(item.func) == "api_view"
            ),
            None,
        )
        if decorator is None:
            raise InventoryError(f"{function.name}: expected a literal @api_view")
        endpoints.update(
            (method.upper(), route) for method in literal(decorator.args[0])
        )
    return base, endpoints


def documented_endpoints(text):
    return set(
        re.findall(
            r"^\|\s*(GET|POST|PUT|PATCH|DELETE)\s*\|\s*`([^`]+)`\s*\|",
            text,
            re.MULTILINE,
        )
    )


def check_documents(root, base, endpoints):
    directory = root / "docs/backend/api"
    documents = {
        path: path.read_text(encoding="utf-8") for path in directory.glob("*.md")
    }
    index = directory / "README.md"
    if index not in documents:
        raise InventoryError(f"Missing API index: {index}")
    for label, actual, expected in (
        ("index", documented_endpoints(documents[index]), endpoints),
        (
            "individual specifications",
            set().union(
                *(
                    documented_endpoints(text)
                    for path, text in documents.items()
                    if path != index
                )
            ),
            endpoints - {("GET", base)},
        ),
    ):
        if actual != expected:
            raise InventoryError(
                f"{label}: missing={sorted(expected - actual)}, "
                f"unexpected={sorted(actual - expected)}"
            )
    json_count = 0
    link_count = 0
    for path, text in documents.items():
        for sample in re.findall(r"```json\n(.*?)\n```", text, re.DOTALL):
            try:
                json.loads(sample)
            except ValueError as error:
                raise InventoryError(
                    f"{path.name}: invalid JSON example: {error}"
                ) from error
            json_count += 1
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            if not (path.parent / unquote(parsed.path)).exists():
                raise InventoryError(f"{path.name}: broken local link: {target}")
            link_count += 1
    return len(documents), json_count, link_count


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
        help="Repository root (default: derived from script location)",
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument(
        "--json", action="store_true", help="Print method/path records as JSON"
    )
    output.add_argument(
        "--check-docs",
        action="store_true",
        help="Check API tables, JSON examples, and local links",
    )
    args = parser.parse_args(argv)
    try:
        base, endpoints = collect_endpoints(args.root.resolve())
        if args.check_docs:
            counts = check_documents(args.root.resolve(), base, endpoints)
            print(
                f"PASS: {len(endpoints)} operations, "
                f"{counts[0]} documents, {counts[1]} JSON examples, "
                f"{counts[2]} local links"
            )
        elif args.json:
            print(
                json.dumps(
                    [
                        {"method": method, "path": path}
                        for method, path in sorted(endpoints)
                    ],
                    indent=2,
                )
            )
        else:
            print("| Method | Path |\n| --- | --- |")
            for method, path in sorted(endpoints, key=lambda item: (item[1], item[0])):
                print(f"| {method} | `{path}` |")
    except (InventoryError, OSError, SyntaxError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

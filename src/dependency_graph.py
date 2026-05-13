"""
Build a dependency graph for a FiveM resources folder.

For each resource:
- declared dependencies via `dependency '...'` / `dependencies { ... }`
- declared exports
- implicit `@resource/file.lua` references from shared_scripts/client_scripts
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from fivem_utils import find_resources


@dataclass
class ResourceNode:
    name: str
    path: str
    dependencies: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    referenced_by: list[str] = field(default_factory=list)
    missing_deps: list[str] = field(default_factory=list)
    has_manifest: bool = True


@dataclass
class DependencyGraph:
    nodes: dict[str, ResourceNode]
    cycles: list[list[str]]

    def topological_layers(self) -> list[list[str]]:
        """Return resources grouped by dependency depth (roots first)."""
        depth: dict[str, int] = {}

        def compute(name: str, stack: set[str]) -> int:
            if name in depth:
                return depth[name]
            if name in stack:
                return 0
            stack.add(name)
            node = self.nodes.get(name)
            if not node or not node.dependencies:
                depth[name] = 0
                return 0
            d = 1 + max(
                (compute(dep, stack) for dep in node.dependencies if dep in self.nodes),
                default=0,
            )
            depth[name] = d
            stack.discard(name)
            return d

        for n in self.nodes:
            compute(n, set())
        layers: dict[int, list[str]] = {}
        for name, d in depth.items():
            layers.setdefault(d, []).append(name)
        return [sorted(layers[k]) for k in sorted(layers.keys())]


_DEP_BLOCK = re.compile(r"dependenc(?:y|ies)\s*\{([^}]+)\}", re.DOTALL | re.IGNORECASE)
_DEP_SINGLE = re.compile(r"^\s*dependency\s+['\"]([^'\"]+)['\"]", re.MULTILINE | re.IGNORECASE)
_EXPORTS_BLOCK = re.compile(r"exports?\s*\{([^}]+)\}", re.DOTALL | re.IGNORECASE)
_AT_REF = re.compile(r"['\"]@([\w\-]+)/", re.IGNORECASE)


def _collect_manifest_text(resource_dir: Path) -> str:
    candidates = [resource_dir / "fxmanifest.lua", resource_dir / "__resource.lua"]
    for c in candidates:
        if c.exists():
            try:
                return c.read_text(encoding="utf-8", errors="replace")
            except Exception:
                return ""
    return ""


def _iter_resources(root: Path):
    """Yield (name, path) for every resource directory under ``root`` (recursive)."""
    for resource_dir in find_resources(root):
        yield resource_dir.name, resource_dir


def build_graph(resources_path: str) -> DependencyGraph:
    root = Path(resources_path)
    nodes: dict[str, ResourceNode] = {}

    for name, path in _iter_resources(root):
        text = _collect_manifest_text(path)
        deps: set[str] = set()
        for m in _DEP_BLOCK.finditer(text):
            for token in re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)):
                deps.add(token)
        for m in _DEP_SINGLE.finditer(text):
            deps.add(m.group(1))

        exports: list[str] = []
        for m in _EXPORTS_BLOCK.finditer(text):
            exports.extend(re.findall(r"['\"]([^'\"]+)['\"]", m.group(1)))

        # implicit deps: @other/foo.lua references
        for m in _AT_REF.finditer(text):
            deps.add(m.group(1))

        nodes[name] = ResourceNode(
            name=name,
            path=str(path),
            dependencies=sorted(deps),
            exports=sorted(set(exports)),
        )

    # reverse refs + missing dep detection
    for node in nodes.values():
        for dep in node.dependencies:
            if dep in nodes:
                nodes[dep].referenced_by.append(node.name)
            else:
                node.missing_deps.append(dep)
    for node in nodes.values():
        node.referenced_by = sorted(set(node.referenced_by))

    cycles = _detect_cycles(nodes)
    return DependencyGraph(nodes=nodes, cycles=cycles)


def _detect_cycles(nodes: dict[str, ResourceNode]) -> list[list[str]]:
    """Return a list of cycles. Each cycle is a list of resource names."""
    cycles: list[list[str]] = []
    visited: dict[str, int] = {}  # 0=unvisited, 1=on stack, 2=done

    def visit(name: str, stack: list[str]) -> None:
        state = visited.get(name, 0)
        if state == 2:
            return
        if state == 1:
            idx = stack.index(name)
            cycle = stack[idx:] + [name]
            cycles.append(cycle)
            return
        visited[name] = 1
        stack.append(name)
        node = nodes.get(name)
        if node:
            for dep in node.dependencies:
                if dep in nodes:
                    visit(dep, stack)
        stack.pop()
        visited[name] = 2

    for n in nodes:
        visit(n, [])

    seen: set[tuple[str, ...]] = set()
    unique: list[list[str]] = []
    for c in cycles:
        key = tuple(sorted(c))
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique

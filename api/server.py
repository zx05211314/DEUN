"""FastAPI server to expose per-book analysis outputs as JSON/JSON-LD."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "output"

app = FastAPI(title="Novel Semantic API", version="1.0.0")


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def book_dir(book: str) -> Path:
    return OUTPUT_ROOT / book


def list_books() -> List[str]:
    return sorted([p.name for p in OUTPUT_ROOT.iterdir() if p.is_dir() and (p / "semantic_relations.json").exists()])


@app.get("/books")
def get_books():
    return {"books": list_books()}


def ensure_book(book: str) -> Path:
    bdir = book_dir(book)
    if not bdir.exists():
        raise HTTPException(status_code=404, detail=f"Book '{book}' not found")
    return bdir


def load_book_json(book: str, filename: str) -> Any:
    bdir = ensure_book(book)
    data = load_json(bdir / filename)
    if data is None:
        raise HTTPException(status_code=404, detail=f"File '{filename}' not found for book '{book}'")
    return data


@app.get("/books/{book}/items")
def get_items(book: str):
    return load_book_json(book, "items.json")


@app.get("/books/{book}/relations")
def get_relations(book: str):
    return load_book_json(book, "relations.json")


@app.get("/books/{book}/inferred_relations")
def get_inferred_relations(book: str):
    return load_book_json(book, "inferred_relations.json")


@app.get("/books/{book}/semantic_relations")
def get_semantic_relations(book: str):
    return load_book_json(book, "semantic_relations.json")


@app.get("/books/{book}/character_relations")
def get_character_relations(book: str):
    return load_book_json(book, "character_relations.json")


@app.get("/books/{book}/semantic_graph")
def get_semantic_graph(book: str):
    return load_book_json(book, "semantic_graph.json")


@app.get("/books/{book}/jsonld")
def get_jsonld(book: str):
    """Simple JSON-LD view over semantic_graph nodes/edges."""
    graph = load_book_json(book, "semantic_graph.json")
    ctx = {
        "@context": {
            "id": "@id",
            "type": "@type",
            "label": "http://schema.org/name",
            "Character": "http://schema.org/Person",
            "Item": "http://schema.org/Product",
            "Mission": "http://schema.org/Action",
            "Emotion": "http://schema.org/Emotion",
            "uses": "http://schema.org/uses",
        }
    }
    nodes = []
    for n in graph.get("nodes", []):
        nodes.append({"@id": f"node/{n['id']}", "@type": n.get("type", "Thing"), "label": n.get("label", "")})
    edges = []
    for e in graph.get("edges", []):
        edges.append(
            {
                "@id": f"edge/{e.get('source')}-{e.get('target')}",
                "@type": "uses",
                "source": f"node/{e.get('source')}",
                "target": f"node/{e.get('target')}",
                "verb": e.get("verb", ""),
                "action_type": e.get("action_type", ""),
                "mission_type": e.get("mission_type", ""),
            }
        )
    return JSONResponse({**ctx, "nodes": nodes, "edges": edges})


# Run with: uvicorn api.server:app --reload --port 8000

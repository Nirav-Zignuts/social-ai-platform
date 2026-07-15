"""Knowledge retrieval / Chroma desync regression tests."""

import uuid
from unittest.mock import patch

import pytest
from langchain_core.embeddings import FakeEmbeddings

from app.knowledge.retrieval import retrieve_context
from app.knowledge.vectorstore import (
    collection_vector_count,
    get_chroma_persist_dir,
    index_chunks,
    rehydrate_workspace_vectors_from_db,
)
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_document import KnowledgeDocument
from app.services.generation.nodes import check_hard_rules


@pytest.fixture
def fake_embeddings():
    return FakeEmbeddings(size=8)


@pytest.fixture
def chroma_tmpdir(tmp_path, monkeypatch):
    persist = tmp_path / "chroma"
    persist.mkdir()
    abs_path = str(persist.resolve())
    monkeypatch.setattr(
        "app.knowledge.vectorstore.settings.CHROMA_PERSIST_DIR", abs_path
    )
    monkeypatch.setattr("app.knowledge.vectorstore.CHROMA_PERSIST_DIR", abs_path)
    monkeypatch.setattr(
        "app.knowledge.retrieval.get_chroma_persist_dir", lambda: abs_path
    )
    return abs_path


@pytest.fixture
def indexed_document(db, workspace):
    doc = KnowledgeDocument(
        workspace_id=workspace.id,
        file_name="leafling_kb.pdf",
        file_type="pdf",
        file_path="https://example.com/leafling_kb.pdf",
        status="indexed",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    texts = [
        "Leafling Urban Nursery is a plant shop in Pune offering Repotting Sunday "
        "and free plant hospital consultations on Wednesday and Saturday.",
        "We carry Monstera Deliciosa, Peace Lily, Philodendron Birkin, and handmade "
        "ceramic pots for houseplant parents who feel intimidated.",
    ]
    for i, text in enumerate(texts):
        db.add(
            KnowledgeChunk(
                document_id=doc.id,
                workspace_id=workspace.id,
                chunk_text=text,
                chunk_index=i,
                chroma_id=f"stale-{uuid.uuid4()}",
            )
        )
    db.commit()
    return doc, texts


def test_check_hard_rules_detects_prohibited_and_missing():
    result = check_hard_rules(
        caption="This plant is foolproof and perfect for beginners",
        hashtags=["#plants"],
        cta="Shop now",
        prohibited_words=["foolproof", "unkillable"],
        required_keywords=["Leafling"],
    )
    assert "foolproof" in result["violations"]
    assert "Leafling" in result["missing_required"]


def test_check_hard_rules_passes_when_compliant():
    result = check_hard_rules(
        caption="Visit Leafling for gentle plant care tips",
        hashtags=["#Leafling"],
        cta="Say hi",
        prohibited_words=["foolproof"],
        required_keywords=["Leafling"],
    )
    assert result["violations"] == []
    assert result["missing_required"] == []


@patch("app.knowledge.vectorstore._get_ingestion_embeddings")
@patch("app.knowledge.vectorstore.get_retrieval_embeddings")
@patch("app.knowledge.retrieval.get_retrieval_embeddings")
def test_retrieve_context_returns_chunks_after_index(
    mock_ret_emb,
    mock_vs_ret_emb,
    mock_ing_emb,
    db,
    workspace,
    indexed_document,
    chroma_tmpdir,
    fake_embeddings,
):
    """Indexed document + vectors in Chroma must yield retrieval hits."""
    mock_ret_emb.return_value = fake_embeddings
    mock_vs_ret_emb.return_value = fake_embeddings
    mock_ing_emb.return_value = fake_embeddings

    doc, texts = indexed_document
    chroma_ids = index_chunks(str(workspace.id), str(doc.id), texts)
    assert len(chroma_ids) == len(texts)
    assert collection_vector_count(str(workspace.id)) == len(texts)

    results = retrieve_context(
        str(workspace.id),
        "What days does Leafling offer plant hospital consultations?",
        k=5,
    )
    assert len(results) > 0
    joined = " ".join(r.get("text") or r.get("chunk_text") or "" for r in results)
    assert "plant hospital" in joined.lower() or "leafling" in joined.lower()


@patch("app.knowledge.vectorstore._get_ingestion_embeddings")
@patch("app.knowledge.vectorstore.get_retrieval_embeddings")
@patch("app.knowledge.retrieval.get_retrieval_embeddings")
def test_retrieve_rehydrates_when_chroma_empty_but_postgres_has_chunks(
    mock_ret_emb,
    mock_vs_ret_emb,
    mock_ing_emb,
    db,
    workspace,
    indexed_document,
    chroma_tmpdir,
    fake_embeddings,
):
    """
    Regression: status=indexed + knowledge_chunks rows, but Chroma collection
    empty → retrieve must rebuild vectors and still return results.
    """
    mock_ret_emb.return_value = fake_embeddings
    mock_vs_ret_emb.return_value = fake_embeddings
    mock_ing_emb.return_value = fake_embeddings

    assert collection_vector_count(str(workspace.id)) == 0

    written = rehydrate_workspace_vectors_from_db(str(workspace.id))
    assert written > 0
    assert collection_vector_count(str(workspace.id)) > 0

    results = retrieve_context(
        str(workspace.id),
        "Leafling Urban Nursery Repotting Sunday plant shop Pune",
        k=5,
    )
    assert len(results) > 0


def test_chroma_persist_dir_is_absolute(chroma_tmpdir):
    path = get_chroma_persist_dir()
    assert path == chroma_tmpdir
    assert path.startswith("/")

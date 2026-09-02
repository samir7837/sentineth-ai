"""End-to-end regression tests for the document RAG pipeline.

Covers upload -> extract -> chunk -> embed -> index -> retrieve -> answer
using in-memory providers. These are the guardrails AGENTS.md section 34 asks
for.
"""

from tests.pdf_builder import build_pdf


REVENUE_PDF = build_pdf(
    [
        "Sentineth Q3 planning notes.",
        "The revenue target for Q3 is four million dollars.",
        "Project Atlas is blocked on vendor security review.",
    ]
)

HIRING_PDF = build_pdf(
    [
        "Sentineth hiring plan.",
        "We plan to hire two backend engineers in Q3.",
        "Recruiting is owned by the operations team.",
    ]
)


def upload(client, organization_id, filename, content):
    return client.post(
        f"/organizations/{organization_id}/documents",
        files=(
            (
                "file",
                (filename, content, "application/pdf"),
            ),
        ),
    )


def test_health_and_root():
    # No fixtures: these must work with nothing configured.
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "healthy"}
        assert client.get("/").json()["name"] == "Sentineth AI"


def test_upload_extracts_chunks_and_indexes(
    client, organization, vector_store
):
    org_id = organization()

    response = upload(client, org_id, "q3-planning.pdf", REVENUE_PDF)

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["status"] == "READY"
    assert body["filename"] == "q3-planning.pdf"
    assert body["chunks"] >= 1
    assert body["file_size"] == len(REVENUE_PDF)

    # Vectors reached the store, stamped with the owning organization.
    assert len(vector_store.points) == body["chunks"]

    for point in vector_store.points.values():
        assert point["payload"]["organization_id"] == org_id
        assert point["payload"]["filename"] == "q3-planning.pdf"


def test_query_returns_answer_with_filename_citation(
    client, organization, llm_provider
):
    """Regression: sources[].filename used to always be null.

    `retrieval_service` dropped `filename` from the Qdrant payload while
    `query_service` read it, so every citation came back unattributed.
    """
    org_id = organization()

    assert upload(
        client, org_id, "q3-planning.pdf", REVENUE_PDF
    ).status_code == 200

    response = client.post(
        f"/organizations/{org_id}/query",
        json={"query": "What is the revenue target for Q3?"},
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["answer"] == "Fake grounded answer."
    assert body["sources"], "expected at least one citation"

    source = body["sources"][0]
    assert source["filename"] == "q3-planning.pdf"
    assert source["document_id"]
    assert source["chunk_id"]
    assert source["score"] is not None

    # The retrieved text was actually put in front of the model, and the
    # anti-injection system prompt was included.
    messages = llm_provider.calls[0]
    assert messages[0]["role"] == "system"
    assert "untrusted" in messages[0]["content"].lower()
    assert "revenue target" in messages[1]["content"].lower()


def test_search_returns_filename_and_content(client, organization):
    org_id = organization()

    assert upload(
        client, org_id, "q3-planning.pdf", REVENUE_PDF
    ).status_code == 200

    response = client.post(
        f"/organizations/{org_id}/search",
        json={"query": "revenue target", "limit": 5},
    )

    assert response.status_code == 200, response.text
    results = response.json()["results"]

    assert results
    assert results[0]["filename"] == "q3-planning.pdf"
    assert "revenue target" in results[0]["content"].lower()


def test_retrieval_ranks_the_relevant_document_first(client, organization):
    org_id = organization()

    assert upload(
        client, org_id, "q3-planning.pdf", REVENUE_PDF
    ).status_code == 200
    assert upload(
        client, org_id, "hiring-plan.pdf", HIRING_PDF
    ).status_code == 200

    response = client.post(
        f"/organizations/{org_id}/search",
        json={"query": "how many backend engineers are we hiring", "limit": 2},
    )

    assert response.status_code == 200, response.text
    results = response.json()["results"]

    assert len(results) == 2
    assert results[0]["filename"] == "hiring-plan.pdf"


def test_organization_isolation_on_search_and_query(client, organization):
    """A second organization must not see the first one's documents."""

    org_a = organization("Org A")
    org_b = organization("Org B")

    assert upload(
        client, org_a, "q3-planning.pdf", REVENUE_PDF
    ).status_code == 200

    search = client.post(
        f"/organizations/{org_b}/search",
        json={"query": "revenue target"},
    )
    assert search.status_code == 200, search.text
    assert search.json()["results"] == []

    query = client.post(
        f"/organizations/{org_b}/query",
        json={"query": "What is the revenue target for Q3?"},
    )
    assert query.status_code == 200, query.text

    body = query.json()
    assert body["sources"] == []
    assert "couldn't find enough relevant information" in body["answer"]


def test_non_pdf_upload_is_rejected(client, organization, vector_store):
    org_id = organization()

    response = client.post(
        f"/organizations/{org_id}/documents",
        files=(("file", ("notes.txt", b"plain text notes", "text/plain")),),
    )

    # TODO: this should be 415 Unsupported Media Type, not 500. The
    # endpoint currently maps every ValueError to 500.
    assert response.status_code == 500
    assert vector_store.points == {}


def test_empty_upload_is_rejected(client, organization):
    org_id = organization()

    response = client.post(
        f"/organizations/{org_id}/documents",
        files=(("file", ("empty.pdf", b"", "application/pdf")),),
    )

    assert response.status_code == 500


def test_query_validation_rejects_blank_and_oversized_limit(
    client, organization
):
    org_id = organization()

    assert client.post(
        f"/organizations/{org_id}/query",
        json={"query": "   "},
    ).status_code == 400

    assert client.post(
        f"/organizations/{org_id}/query",
        json={"query": "anything", "limit": 999},
    ).status_code == 422

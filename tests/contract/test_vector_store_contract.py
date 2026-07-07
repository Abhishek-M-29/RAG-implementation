import pytest
from langchain_core.documents import Document
from ragframework.vectorstores.registry import VECTOR_STORE_REGISTRY


def _config_for(name, tmp_path):
    if name == "faiss":
        from langchain_huggingface import HuggingFaceEmbeddings
        return {
            "index_path": str(tmp_path / "faiss_index"),
            "embedding_model": HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            ),
        }
    msg = f"test_config_for has no config for {name!r}"
    raise ValueError(msg)


@pytest.mark.parametrize("name,cls", VECTOR_STORE_REGISTRY.items())
def test_add_search_delete_roundtrip(name, cls, tmp_path):
    config = _config_for(name, tmp_path)

    docs = [
        Document(
            page_content="Apple banana fruit are delicious and healthy.",
            metadata={"id": "ct-id-1", "source": "contract-test"},
        ),
        Document(
            page_content="Dog cat animal are popular pets in households.",
            metadata={"id": "ct-id-2", "source": "contract-test"},
        ),
        Document(
            page_content="Machine learning artificial intelligence is transforming technology.",
            metadata={"id": "ct-id-3", "source": "contract-test"},
        ),
    ]

    store = cls.from_config(config)

    ids = store.add_documents(docs)
    assert len(ids) == len(docs)

    results = store.similarity_search("fruit apple banana", k=3)
    assert results, "Expected results after adding documents"
    pre_delete_contents = {d.page_content for d in results}

    store.delete(ids)

    results_after = store.similarity_search("fruit apple banana", k=3)
    assert store.health_check(), "Store should be healthy after delete"

    for doc in results_after:
        assert doc.metadata.get("id") not in ids, (
            f"Deleted document {doc.metadata.get('id')} still appears in search results"
        )
    after_contents = {d.page_content for d in results_after}
    assert not (pre_delete_contents & after_contents) or not after_contents, (
        "Deleted content should not appear in search results, "
        "or store should return empty if all docs were deleted"
    )

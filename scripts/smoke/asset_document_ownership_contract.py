#!/usr/bin/env python3
"""Fail-fast source/migration proof for first-class Asset and Document ownership."""

from pathlib import Path


def read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def require(text: str, needle: str, *, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label} is missing required contract: {needle}")


def forbid(text: str, needle: str, *, label: str) -> None:
    if needle in text:
        raise AssertionError(f"{label} still contains deprecated ownership contract: {needle}")


def main() -> None:
    migration = read("services/core/migrations/versions/0018_asset_document_ownership.py")
    models = read("services/core/src/kairo_core/models.py")
    document_models = read("services/core/src/kairo_core/document_models.py")
    assets = read("services/core/src/kairo_core/assets.py")
    documents = read("services/core/src/kairo_core/documents.py")
    knowledge = read("services/core/src/kairo_core/knowledge.py")
    ownership = read("services/core/src/kairo_core/ownership.py")

    for table in ("assets", "documents"):
        require(migration, f'op.add_column("{table}"', label="migration 0018")
        require(migration, 'sa.Column("keycloak_subject"', label="migration 0018")
    require(migration, "trg_asset_project_owner", label="migration 0018")
    require(migration, "trg_document_owner_bindings", label="migration 0018")

    require(models, "class Asset(Base):", label="Asset model")
    require(models, "keycloak_subject: Mapped[str]", label="Asset model")
    require(document_models, "class Document(Base):", label="Document model")
    require(document_models, "keycloak_subject: Mapped[str]", label="Document model")

    require(assets, "keycloak_subject=principal.subject", label="Asset create path")
    require(assets, "Asset.keycloak_subject == principal.subject", label="Asset list path")
    require(documents, "keycloak_subject=principal.subject", label="Document create path")
    require(documents, "Document.keycloak_subject == principal.subject", label="Document public paths")
    require(knowledge, "Document.keycloak_subject == principal.subject", label="Knowledge search")
    require(ownership, "Document.keycloak_subject == subject", label="Graph/entity ownership")
    require(ownership, "Asset.keycloak_subject == subject", label="Graph/entity ownership")

    # JSON metadata can still contain ordinary display/provenance details, but it is no longer the
    # canonical tenant boundary for these entities.
    forbid(assets, 'metadata_json["owner_subject"]', label="Asset API")
    forbid(documents, 'metadata_json["owner_subject"]', label="Document API")
    forbid(knowledge, 'metadata_json["owner_subject"]', label="Knowledge API")

    print("KAIRO Asset/Document canonical ownership contract passed")


if __name__ == "__main__":
    main()

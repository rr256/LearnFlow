"""Contract tests for a resource's stored PDF files (RES-014 to RES-017).

These run over the real application factory and the real use case, with only the
repositories, the byte storage, and the PDF inspector replaced — so they exercise
routing, multipart parsing, validation mapping, response shaping, and the
download headers over the code the running backend uses.

**No test here writes to a filesystem.** Bytes go to an in-memory fake, so the
configured volume is never touched and nothing is left behind.
"""

import uuid

from app.application.dto.resource_file import MAX_FILE_BYTES, MAX_FILES_PER_RESOURCE

RESOURCES = "/api/v1/resources"
FILES = "/api/v1/resource-files"
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


def register(client, topic_ids, **fields):
    body = {
        "resource_type": "pdf",
        "title": "Operating Systems notes",
        "source_label": "Blue binder",
        "topic_ids": [str(topic_id) for topic_id in topic_ids],
    }
    body.update(fields)
    response = client.post(RESOURCES, json=body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def upload(client, resource_id, *, filename="chapter.pdf", content=PDF):
    return client.post(
        f"{RESOURCES}/{resource_id}/files",
        files={"file": (filename, content, "application/pdf")},
    )


def stored(client, resource_id, **params):
    response = client.get(f"{RESOURCES}/{resource_id}/files", params=params)
    assert response.status_code == 200, response.text
    return response.json()["data"]


# -- storing ------------------------------------------------------------------


def test_a_pdf_is_stored_and_described(resource_files_client, cataloguing, file_storage):
    resource = register(resource_files_client, [cataloguing.topic.id])

    response = upload(resource_files_client, resource["id"], filename="Chapter 3.pdf")

    assert response.status_code == 201, response.text
    data = response.json()["data"]
    assert data["original_filename"] == "Chapter 3.pdf"
    assert data["byte_size"] == len(PDF)
    assert data["page_count"] == 3
    assert data["content_type"] == "application/pdf"
    assert data["status"] == "active"
    assert len(data["checksum"]) == 64
    assert len(file_storage.written) == 1


def test_no_response_ever_carries_a_storage_location(resource_files_client, cataloguing):
    """The endpoint rule: no resource endpoint returns a storage path."""
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"])

    body = created.text + resource_files_client.get(f"{RESOURCES}/{resource['id']}/files").text

    assert "storage_key" not in body
    assert "/var/lib" not in body
    assert set(created.json()["data"]) == {
        "id",
        "resource_id",
        "original_filename",
        "byte_size",
        "page_count",
        "content_type",
        "checksum",
        "status",
        "created_at",
        "updated_at",
    }


def test_several_files_live_against_one_resource(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])

    upload(resource_files_client, resource["id"], filename="one.pdf")
    upload(resource_files_client, resource["id"], filename="two.pdf")

    listed = stored(resource_files_client, resource["id"])
    assert [f["original_filename"] for f in listed] == ["two.pdf", "one.pdf"]


# -- refusals -----------------------------------------------------------------


def test_a_non_pdf_is_refused(resource_files_client, cataloguing, file_storage):
    resource = register(resource_files_client, [cataloguing.topic.id])

    response = resource_files_client.post(
        f"{RESOURCES}/{resource['id']}/files",
        files={"file": ("notes.txt", b"just text", "text/plain")},
    )

    assert response.status_code == 422, response.text
    assert file_storage.written == {}
    assert stored(resource_files_client, resource["id"]) == []


def test_a_file_claiming_to_be_a_pdf_is_refused_on_its_bytes(
    resource_files_client, cataloguing, file_storage
):
    """An extension is a claim; the signature is evidence."""
    resource = register(resource_files_client, [cataloguing.topic.id])

    response = upload(resource_files_client, resource["id"], content=b"MZ not a pdf")

    assert response.status_code == 422, response.text
    assert file_storage.written == {}


def test_an_encrypted_pdf_is_refused(
    resource_files_client, cataloguing, document_inspector, file_storage
):
    document_inspector.is_encrypted = True
    resource = register(resource_files_client, [cataloguing.topic.id])

    response = upload(resource_files_client, resource["id"])

    assert response.status_code == 422, response.text
    assert "password" in response.json()["error"]["message"].lower()
    assert file_storage.written == {}


def test_an_unreadable_pdf_is_refused(
    resource_files_client, cataloguing, document_inspector, file_storage
):
    document_inspector.unreadable = True
    resource = register(resource_files_client, [cataloguing.topic.id])

    response = upload(resource_files_client, resource["id"])

    assert response.status_code == 422, response.text
    assert file_storage.written == {}


def test_an_oversized_upload_is_refused_as_too_large(
    resource_files_client, cataloguing, file_storage
):
    """Refused between chunks, so the whole body is never held."""
    resource = register(resource_files_client, [cataloguing.topic.id])

    response = upload(
        resource_files_client,
        resource["id"],
        content=b"%PDF-" + b"x" * MAX_FILE_BYTES,
    )

    assert response.status_code == 413, response.text
    assert file_storage.written == {}


def test_too_many_pages_is_refused_as_too_large(
    resource_files_client, cataloguing, document_inspector
):
    document_inspector.page_count = 5000
    resource = register(resource_files_client, [cataloguing.topic.id])

    assert upload(resource_files_client, resource["id"]).status_code == 413


def test_no_refusal_repeats_the_filename(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    secret = "my-private-thesis-draft.txt"

    response = resource_files_client.post(
        f"{RESOURCES}/{resource['id']}/files",
        files={"file": (secret, b"just text", "text/plain")},
    )

    assert secret not in response.text


def test_a_resource_may_not_exceed_its_file_ceiling(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    for index in range(MAX_FILES_PER_RESOURCE):
        assert (
            upload(resource_files_client, resource["id"], filename=f"{index}.pdf").status_code
            == 201
        )

    assert upload(resource_files_client, resource["id"], filename="extra.pdf").status_code == 409


def test_an_unknown_resource_is_a_404(resource_files_client):
    assert upload(resource_files_client, uuid.uuid4()).status_code == 404


def test_archived_material_accepts_no_new_file(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    archived = resource_files_client.patch(
        f"{RESOURCES}/{resource['id']}", json={"status": "archived"}
    )
    assert archived.status_code == 200, archived.text

    assert upload(resource_files_client, resource["id"]).status_code == 409


# -- downloading --------------------------------------------------------------


def test_a_stored_file_downloads_byte_for_byte(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]

    response = resource_files_client.get(f"{FILES}/{created['id']}/content")

    assert response.status_code == 200, response.text
    assert response.content == PDF
    assert response.headers["content-type"] == "application/pdf"


def test_a_download_is_an_attachment_and_not_sniffable(resource_files_client, cataloguing):
    """A PDF is active content: the browser saves it rather than rendering it."""
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"], filename="Chapter 3.pdf").json()["data"]

    response = resource_files_client.get(f"{FILES}/{created['id']}/content")

    disposition = response.headers["content-disposition"]
    assert disposition.startswith("attachment;")
    assert "Chapter%203.pdf" in disposition
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "no-store" in response.headers["cache-control"]


def test_a_filename_cannot_break_the_download_header(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(
        resource_files_client, resource["id"], filename='ev"il\r\nX-Injected: yes.pdf'
    ).json()["data"]

    response = resource_files_client.get(f"{FILES}/{created['id']}/content")

    assert "x-injected" not in {name.lower() for name in response.headers}
    assert '"' not in response.headers["content-disposition"].split("''")[-1]


def test_an_unknown_file_is_a_404(resource_files_client):
    assert resource_files_client.get(f"{FILES}/{uuid.uuid4()}/content").status_code == 404


def test_an_archived_file_is_still_downloadable(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]
    resource_files_client.patch(f"{FILES}/{created['id']}", json={"status": "archived"})

    assert resource_files_client.get(f"{FILES}/{created['id']}/content").status_code == 200


# -- setting aside ------------------------------------------------------------


def test_a_file_moves_between_statuses_in_both_directions(
    resource_files_client, cataloguing, file_storage
):
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]

    aside = resource_files_client.patch(f"{FILES}/{created['id']}", json={"status": "archived"})
    back = resource_files_client.patch(f"{FILES}/{created['id']}", json={"status": "active"})

    assert aside.json()["data"]["status"] == "archived"
    assert back.json()["data"]["status"] == "active"
    # Nothing was removed at any point.
    assert len(file_storage.written) == 1


def test_a_status_filter_narrows_the_list(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    first = upload(resource_files_client, resource["id"], filename="a.pdf").json()["data"]
    upload(resource_files_client, resource["id"], filename="b.pdf")
    resource_files_client.patch(f"{FILES}/{first['id']}", json={"status": "archived"})

    assert len(stored(resource_files_client, resource["id"], status="active")) == 1
    assert len(stored(resource_files_client, resource["id"])) == 2


def test_an_unknown_status_is_refused(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]

    response = resource_files_client.patch(f"{FILES}/{created['id']}", json={"status": "deleted"})

    assert response.status_code == 422, response.text


def test_a_body_field_beyond_status_is_refused(resource_files_client, cataloguing):
    """Nothing else about a stored file may move."""
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]

    response = resource_files_client.patch(
        f"{FILES}/{created['id']}",
        json={"status": "archived", "original_filename": "renamed.pdf"},
    )

    assert response.status_code == 422, response.text


def test_archived_material_freezes_its_files(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]
    resource_files_client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    response = resource_files_client.patch(f"{FILES}/{created['id']}", json={"status": "archived"})

    assert response.status_code == 409, response.text


def test_archived_material_still_lists_its_files(resource_files_client, cataloguing):
    """Read-only, not unreadable."""
    resource = register(resource_files_client, [cataloguing.topic.id])
    upload(resource_files_client, resource["id"])
    resource_files_client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    assert len(stored(resource_files_client, resource["id"])) == 1


# -- what does not exist ------------------------------------------------------


def test_a_stored_file_can_be_removed_permanently(resource_files_client, cataloguing, file_storage):
    """RES-018 — the one endpoint in LearnFlow that destroys learner data."""
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]

    removed = resource_files_client.delete(f"{FILES}/{created['id']}")

    assert removed.status_code == 204, removed.text
    assert removed.content == b""
    assert stored(resource_files_client, resource["id"]) == []
    assert file_storage.written == {}


def test_removing_the_same_file_twice_is_a_404(resource_files_client, cataloguing):
    """The learner is naming something that no longer exists."""
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]

    assert resource_files_client.delete(f"{FILES}/{created['id']}").status_code == 204
    assert resource_files_client.delete(f"{FILES}/{created['id']}").status_code == 404


def test_removing_an_unknown_file_is_a_404(resource_files_client):
    assert resource_files_client.delete(f"{FILES}/{uuid.uuid4()}").status_code == 404


def test_a_file_on_archived_material_cannot_be_removed(resource_files_client, cataloguing):
    """Archived material is read-only, and deletion is no exception."""
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]
    resource_files_client.patch(f"{RESOURCES}/{resource['id']}", json={"status": "archived"})

    assert resource_files_client.delete(f"{FILES}/{created['id']}").status_code == 409


def test_an_archived_file_on_live_material_can_be_removed(
    resource_files_client, cataloguing, file_storage
):
    """Shelving and removing are different answers to the same mistake."""
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"]).json()["data"]
    resource_files_client.patch(f"{FILES}/{created['id']}", json={"status": "archived"})

    assert resource_files_client.delete(f"{FILES}/{created['id']}").status_code == 204
    assert file_storage.written == {}


def test_no_endpoint_removes_a_whole_resource(resource_files_client, cataloguing):
    """RES-005 stays unimplemented: only a single file can be removed."""
    resource = register(resource_files_client, [cataloguing.topic.id])

    assert resource_files_client.delete(f"{RESOURCES}/{resource['id']}").status_code == 405
    assert resource_files_client.delete(f"{RESOURCES}/{resource['id']}/files").status_code == 405


def test_no_ingestion_endpoint_appeared(resource_files_client, cataloguing):
    """RES-006 to RES-008 wait on an extractor that does not exist."""
    resource = register(resource_files_client, [cataloguing.topic.id])

    assert resource_files_client.post(f"{RESOURCES}/{resource['id']}/ingestions").status_code == 404
    assert resource_files_client.get(f"{RESOURCES}/{resource['id']}/ingestions").status_code == 404


def test_no_response_carries_extracted_text(resource_files_client, cataloguing):
    resource = register(resource_files_client, [cataloguing.topic.id])
    created = upload(resource_files_client, resource["id"])

    for field in ("text", "extracted_text", "content", "chunks", "embedding"):
        assert field not in created.json()["data"]

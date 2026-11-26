import json
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from workspace.models import GroupMembership, Paper, ResearchGroup

User = get_user_model()

SAMPLE_ARXIV_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/1706.03762v7</id>
    <published>2017-06-12T17:57:34Z</published>
    <title>Attention Is All
      You Need</title>
    <summary>The dominant sequence transduction models are based on complex recurrent or convolutional neural networks.</summary>
    <author><name>Ashish Vaswani</name></author>
    <author><name>Noam Shazeer</name></author>
    <arxiv:doi>10.48550/arXiv.1706.03762</arxiv:doi>
    <link rel="alternate" type="text/html" href="https://arxiv.org/abs/1706.03762v7"/>
  </entry>
</feed>
"""

SAMPLE_EMPTY_ARXIV_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
</feed>
"""

SAMPLE_CROSSREF_JSON = {
    "status": "ok",
    "message": {
        "DOI": "10.1145/3295222.3295349",
        "title": ["Deep Residual Learning for Image Recognition"],
        "author": [
            {"given": "Kaiming", "family": "He"},
            {"given": "Xiangyu", "family": "Zhang"},
        ],
        "published-print": {"date-parts": [[2016, 6, 1]]},
        "URL": "https://doi.org/10.1145/3295222.3295349",
        "abstract": "<jats:p>Deeper neural networks are more difficult to train.</jats:p>",
    },
}


def _mock_urlopen_response(payload: bytes):
    response = MagicMock()
    response.read.return_value = payload
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def group_setup(db):
    alice = User.objects.create_user(username="alice", password="StrongPassword123!")
    outsider = User.objects.create_user(
        username="outsider", password="StrongPassword123!"
    )
    group = ResearchGroup.objects.create(name="Adapter Lab", created_by=alice)
    GroupMembership.objects.create(
        group=group, user=alice, role=GroupMembership.Role.ADMIN
    )
    return {"alice": alice, "outsider": outsider, "group": group}


def test_arxiv_adapter_success_and_errors():
    from workspace.patterns.metadata import (
        ArxivAdapter,
        MetadataProvider,
        get_metadata_adapter,
    )

    assert issubclass(ArxivAdapter, MetadataProvider)
    adapter = get_metadata_adapter("arxiv")
    assert isinstance(adapter, ArxivAdapter)

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_response(SAMPLE_ARXIV_XML),
    ) as mock_open:
        data = adapter.fetch("1706.03762")

    mock_open.assert_called_once()
    assert "export.arxiv.org/api/query?id_list=1706.03762" in mock_open.call_args[0][0]
    assert data == {
        "title": "Attention Is All You Need",
        "authors": "Ashish Vaswani, Noam Shazeer",
        "year": 2017,
        "doi": "10.48550/arXiv.1706.03762",
        "arxiv_id": "1706.03762",
        "url": "https://arxiv.org/abs/1706.03762v7",
        "abstract": (
            "The dominant sequence transduction models are based on complex "
            "recurrent or convolutional neural networks."
        ),
    }

    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_response(SAMPLE_EMPTY_ARXIV_XML),
    ):
        with pytest.raises(ValueError):
            adapter.fetch("9999.99999")


def test_crossref_adapter_success_and_errors():
    from workspace.patterns.metadata import (
        CrossRefAdapter,
        MetadataProvider,
        get_metadata_adapter,
    )

    assert issubclass(CrossRefAdapter, MetadataProvider)
    adapter = get_metadata_adapter("CrossRef")
    assert isinstance(adapter, CrossRefAdapter)

    payload = json.dumps(SAMPLE_CROSSREF_JSON).encode("utf-8")
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_response(payload),
    ) as mock_open:
        data = adapter.fetch("10.1145/3295222.3295349")

    mock_open.assert_called_once()
    assert (
        "api.crossref.org/works/10.1145/3295222.3295349" in mock_open.call_args[0][0]
    )
    assert data == {
        "title": "Deep Residual Learning for Image Recognition",
        "authors": "Kaiming He, Xiangyu Zhang",
        "year": 2016,
        "doi": "10.1145/3295222.3295349",
        "arxiv_id": "",
        "url": "https://doi.org/10.1145/3295222.3295349",
        "abstract": "Deeper neural networks are more difficult to train.",
    }

    with patch(
        "urllib.request.urlopen",
        side_effect=HTTPError(
            url="https://api.crossref.org/works/invalid",
            code=404,
            msg="Not Found",
            hdrs=None,
            fp=BytesIO(b""),
        ),
    ):
        with pytest.raises(ValueError):
            adapter.fetch("invalid-doi")

    with pytest.raises(ValueError):
        get_metadata_adapter("pubmed")


@pytest.mark.django_db
def test_api_import_metadata_endpoint_and_schema(api_client, group_setup):
    alice = group_setup["alice"]
    outsider = group_setup["outsider"]
    group = group_setup["group"]
    endpoint = "/api/papers/import-metadata/"

    # Unauthenticated request denied
    assert (
        api_client.post(
            endpoint,
            {"group": group.id, "source": "arxiv", "identifier": "1706.03762"},
            format="json",
        ).status_code
        in (401, 403)
    )

    # Non-member receives HTTP 403
    api_client.force_authenticate(user=outsider)
    assert (
        api_client.post(
            endpoint,
            {"group": group.id, "source": "arxiv", "identifier": "1706.03762"},
            format="json",
        ).status_code
        == 403
    )

    # Member imports paper via mocked arXiv response
    api_client.force_authenticate(user=alice)
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_response(SAMPLE_ARXIV_XML),
    ):
        resp = api_client.post(
            endpoint,
            {
                "group": group.id,
                "source": "arxiv",
                "identifier": "1706.03762",
                "tags": ["nlp", "Transformers"],
            },
            format="json",
        )
    assert resp.status_code == 201
    assert resp.data["title"] == "Attention Is All You Need"
    assert resp.data["arxiv_id"] == "1706.03762"
    assert set(resp.data["tags"]) == {"nlp", "transformers"}
    assert Paper.objects.filter(group=group, arxiv_id="1706.03762").exists()

    # Invalid source returns HTTP 400
    bad_source = api_client.post(
        endpoint,
        {"group": group.id, "source": "unknown", "identifier": "123"},
        format="json",
    )
    assert bad_source.status_code == 400

    # Invalid identifier returns HTTP 400
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_response(SAMPLE_EMPTY_ARXIV_XML),
    ):
        bad_id = api_client.post(
            endpoint,
            {"group": group.id, "source": "arxiv", "identifier": "9999.99999"},
            format="json",
        )
    assert bad_id.status_code == 400

    # Schema includes /api/papers/import-metadata/
    schema_resp = api_client.get("/api/schema/")
    assert schema_resp.status_code == 200
    assert b"/api/papers/import-metadata/" in schema_resp.content


@pytest.mark.django_db
def test_web_ui_import_metadata_form(client, group_setup):
    alice = group_setup["alice"]
    group = group_setup["group"]
    url = reverse("group-detail", args=[group.id])

    client.force_login(alice)
    payload = json.dumps(SAMPLE_CROSSREF_JSON).encode("utf-8")
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_response(payload),
    ):
        resp = client.post(
            url,
            {
                "action": "import_paper",
                "source": "crossref",
                "identifier": "10.1145/3295222.3295349",
                "tags": "vision, resnet",
            },
        )
    assert resp.status_code == 302
    paper = Paper.objects.get(group=group, doi="10.1145/3295222.3295349")
    assert paper.title == "Deep Residual Learning for Image Recognition"
    assert set(paper.tags.values_list("name", flat=True)) == {"vision", "resnet"}

    # Invalid identifier on Web UI renders form error cleanly (HTTP 200)
    with patch(
        "urllib.request.urlopen",
        return_value=_mock_urlopen_response(SAMPLE_EMPTY_ARXIV_XML),
    ):
        err_resp = client.post(
            url,
            {
                "action": "import_paper",
                "source": "arxiv",
                "identifier": "bad-id",
            },
        )
    assert err_resp.status_code == 200
    assert "No arXiv entry" in err_resp.content.decode()

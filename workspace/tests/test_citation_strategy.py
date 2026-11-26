from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient

from workspace.models import GroupMembership, Paper, ResearchGroup

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def sample_paper_obj():
    return SimpleNamespace(
        title="Attention Is All You Need",
        authors="Ashish Vaswani, Noam Shazeer, Niki Parmar",
        year=2017,
        doi="10.5555/3295222.3295349",
        url="https://arxiv.org/abs/1706.03762",
    )


@pytest.fixture
def group_paper_setup(db):
    alice = User.objects.create_user(username="alice", password="StrongPassword123!")
    outsider = User.objects.create_user(
        username="outsider", password="StrongPassword123!"
    )
    group = ResearchGroup.objects.create(name="NLP Lab", created_by=alice)
    GroupMembership.objects.create(
        group=group, user=alice, role=GroupMembership.Role.ADMIN
    )
    paper = Paper.objects.create(
        group=group,
        added_by=alice,
        title="Attention Is All You Need",
        authors="Ashish Vaswani, Noam Shazeer",
        year=2017,
        doi="10.5555/3295222.3295349",
        url="https://arxiv.org/abs/1706.03762",
    )
    return {"alice": alice, "outsider": outsider, "group": group, "paper": paper}


def test_concrete_citation_strategies(sample_paper_obj):
    from workspace.patterns.citations import (
        APAStrategy,
        BibTeXStrategy,
        CitationStrategy,
        IEEEStrategy,
    )

    assert issubclass(BibTeXStrategy, CitationStrategy)
    assert issubclass(APAStrategy, CitationStrategy)
    assert issubclass(IEEEStrategy, CitationStrategy)

    # BibTeX with DOI
    bib = BibTeXStrategy().format(sample_paper_obj)
    assert bib.startswith("@article{vaswani2017,")
    assert "title={Attention Is All You Need}" in bib
    assert "author={Ashish Vaswani, Noam Shazeer, Niki Parmar}" in bib
    assert "year={2017}" in bib
    assert "doi={10.5555/3295222.3295349}" in bib

    # BibTeX without DOI omits doi field
    no_doi_paper = SimpleNamespace(
        title="Preprint Only",
        authors="Jane Doe",
        year=2024,
        doi="",
        url="https://example.org/preprint",
    )
    bib_no_doi = BibTeXStrategy().format(no_doi_paper)
    assert "@article{doe2024," in bib_no_doi
    assert "doi=" not in bib_no_doi

    # APA with DOI and URL fallback
    apa_doi = APAStrategy().format(sample_paper_obj)
    assert (
        apa_doi
        == "Ashish Vaswani, Noam Shazeer, Niki Parmar (2017). "
        "Attention Is All You Need. https://doi.org/10.5555/3295222.3295349"
    )
    apa_url = APAStrategy().format(no_doi_paper)
    assert apa_url == "Jane Doe (2024). Preprint Only. https://example.org/preprint"

    # IEEE with and without DOI
    ieee_doi = IEEEStrategy().format(sample_paper_obj)
    assert (
        ieee_doi
        == 'Ashish Vaswani, Noam Shazeer, Niki Parmar, "Attention Is All You Need," '
        "2017. doi: 10.5555/3295222.3295349."
    )
    ieee_no_doi = IEEEStrategy().format(no_doi_paper)
    assert ieee_no_doi == 'Jane Doe, "Preprint Only," 2024.'


def test_citation_exporter_runtime_switching_and_factory(sample_paper_obj):
    from workspace.patterns.citations import (
        APAStrategy,
        BibTeXStrategy,
        CitationExporter,
        IEEEStrategy,
        get_citation_strategy,
    )

    exporter = CitationExporter(BibTeXStrategy())
    assert exporter.export(sample_paper_obj).startswith("@article{vaswani2017,")

    exporter.set_strategy(APAStrategy())
    assert "https://doi.org/10.5555/3295222.3295349" in exporter.export(
        sample_paper_obj
    )

    exporter.set_strategy(IEEEStrategy())
    assert '"Attention Is All You Need," 2017.' in exporter.export(sample_paper_obj)

    assert isinstance(get_citation_strategy("bibtex"), BibTeXStrategy)
    assert isinstance(get_citation_strategy("APA"), APAStrategy)
    assert isinstance(get_citation_strategy("ieee"), IEEEStrategy)

    with pytest.raises(ValueError):
        get_citation_strategy("chicago")


@pytest.mark.django_db
def test_api_paper_cite_endpoint_and_schema(api_client, group_paper_setup):
    alice = group_paper_setup["alice"]
    outsider = group_paper_setup["outsider"]
    paper = group_paper_setup["paper"]
    cite_url = f"/api/papers/{paper.id}/cite/"

    # Unauthenticated access is denied
    assert api_client.get(cite_url).status_code in (401, 403)

    # Non-member receives HTTP 403
    api_client.force_authenticate(user=outsider)
    assert api_client.get(cite_url).status_code == 403

    # Member gets default BibTeX citation
    api_client.force_authenticate(user=alice)
    default_resp = api_client.get(cite_url)
    assert default_resp.status_code == 200
    assert default_resp.data["paper_id"] == paper.id
    assert default_resp.data["format"] == "bibtex"
    assert "@article{vaswani2017," in default_resp.data["citation"]

    # Explicit APA and IEEE formats
    apa_resp = api_client.get(f"{cite_url}?format=apa")
    assert apa_resp.status_code == 200
    assert apa_resp.data["format"] == "apa"
    assert "https://doi.org/10.5555/3295222.3295349" in apa_resp.data["citation"]

    ieee_resp = api_client.get(f"{cite_url}?format=ieee")
    assert ieee_resp.status_code == 200
    assert ieee_resp.data["format"] == "ieee"
    assert '"Attention Is All You Need," 2017.' in ieee_resp.data["citation"]

    # Invalid format returns HTTP 400
    invalid_resp = api_client.get(f"{cite_url}?format=chicago")
    assert invalid_resp.status_code == 400

    # Schema documents /api/papers/{id}/cite/
    schema_resp = api_client.get("/api/schema/")
    assert schema_resp.status_code == 200
    assert b"/api/papers/{id}/cite/" in schema_resp.content


@pytest.mark.django_db
def test_paper_detail_view_citation_selector(client, group_paper_setup):
    alice = group_paper_setup["alice"]
    paper = group_paper_setup["paper"]
    url = reverse("paper-detail", args=[paper.id])

    client.force_login(alice)

    # Default BibTeX on paper detail page
    default_resp = client.get(url)
    assert default_resp.status_code == 200
    default_html = default_resp.content.decode()
    assert "@article{vaswani2017," in default_html
    assert 'name="cite_format"' in default_html

    # ?cite_format=apa
    apa_resp = client.get(url, {"cite_format": "apa"})
    assert apa_resp.status_code == 200
    assert (
        "Ashish Vaswani, Noam Shazeer (2017). Attention Is All You Need. "
        "https://doi.org/10.5555/3295222.3295349"
    ) in apa_resp.content.decode()

    # ?cite_format=ieee
    ieee_resp = client.get(url, {"cite_format": "ieee"})
    assert ieee_resp.status_code == 200
    assert (
        "Ashish Vaswani, Noam Shazeer, &quot;Attention Is All You Need,&quot; 2017."
        in ieee_resp.content.decode()
        or 'Ashish Vaswani, Noam Shazeer, "Attention Is All You Need," 2017.'
        in ieee_resp.content.decode()
    )

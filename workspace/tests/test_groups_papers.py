import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user_factory(db):
    def create_user(username="alice", password="StrongPassword123!"):
        return User.objects.create_user(username=username, password=password)

    return create_user


@pytest.mark.django_db
def test_models_and_unique_membership(user_factory):
    from workspace.models import GroupMembership, Paper, ResearchGroup, Tag

    alice = user_factory(username="alice")
    group = ResearchGroup.objects.create(
        name="Vision Lab",
        description="Computer vision research",
        created_by=alice,
    )
    membership = GroupMembership.objects.create(
        group=group,
        user=alice,
        role=GroupMembership.Role.ADMIN,
    )
    assert membership.role == "ADMIN"

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            GroupMembership.objects.create(
                group=group,
                user=alice,
                role=GroupMembership.Role.MEMBER,
            )

    tag = Tag.objects.create(name="  Deep-Learning ")
    assert tag.name == "deep-learning"

    paper = Paper.objects.create(
        group=group,
        added_by=alice,
        title="Attention Is All You Need",
        authors="Ashish Vaswani, Noam Shazeer",
        year=2017,
        doi="10.5555/3295222.3295349",
        arxiv_id="1706.03762",
        url="https://arxiv.org/abs/1706.03762",
        abstract="We propose a new simple network architecture, the Transformer.",
    )
    paper.tags.add(tag)
    assert paper.tags.count() == 1


@pytest.mark.django_db
def test_register_login_and_dashboard_redirect(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login/" in response.url

    reg_response = client.post(
        reverse("register"),
        {
            "username": "newuser",
            "password1": "ComplexPassword123!",
            "password2": "ComplexPassword123!",
        },
    )
    assert reg_response.status_code == 302
    assert User.objects.filter(username="newuser").exists()

    logout_response = client.post(reverse("logout"))
    assert logout_response.status_code == 302

    login_response = client.post(
        reverse("login"),
        {"username": "newuser", "password": "ComplexPassword123!"},
    )
    assert login_response.status_code == 302
    assert client.get("/").status_code == 200


@pytest.mark.django_db
def test_dashboard_creates_group_with_auto_admin_membership(client, user_factory):
    from workspace.models import GroupMembership, ResearchGroup

    alice = user_factory(username="alice")
    bob = user_factory(username="bob")
    other_group = ResearchGroup.objects.create(name="Bob Lab", created_by=bob)
    GroupMembership.objects.create(
        group=other_group, user=bob, role=GroupMembership.Role.ADMIN
    )

    client.force_login(alice)
    response = client.post(
        reverse("dashboard"),
        {
            "name": "NLP Group",
            "description": "Natural language processing papers",
        },
    )
    assert response.status_code == 302

    group = ResearchGroup.objects.get(name="NLP Group")
    assert group.created_by == alice
    membership = GroupMembership.objects.get(group=group, user=alice)
    assert membership.role == GroupMembership.Role.ADMIN

    dash_response = client.get(reverse("dashboard"))
    assert dash_response.status_code == 200
    content = dash_response.content.decode()
    assert "NLP Group" in content
    assert "Bob Lab" not in content


@pytest.mark.django_db
def test_group_detail_access_control_403_for_non_members(client, user_factory):
    from workspace.models import GroupMembership, ResearchGroup

    alice = user_factory(username="alice")
    outsider = user_factory(username="outsider")
    group = ResearchGroup.objects.create(name="Private Lab", created_by=alice)
    GroupMembership.objects.create(
        group=group, user=alice, role=GroupMembership.Role.ADMIN
    )

    client.force_login(outsider)
    get_resp = client.get(reverse("group-detail", args=[group.id]))
    assert get_resp.status_code == 403

    post_resp = client.post(
        reverse("group-detail", args=[group.id]),
        {"action": "add_paper", "title": "Hack", "authors": "X", "year": 2024},
    )
    assert post_resp.status_code == 403


@pytest.mark.django_db
def test_admin_can_add_member_and_non_admin_cannot(client, user_factory):
    from workspace.models import GroupMembership, ResearchGroup

    alice = user_factory(username="alice")
    bob = user_factory(username="bob")
    charlie = user_factory(username="charlie")

    group = ResearchGroup.objects.create(name="Systems Lab", created_by=alice)
    GroupMembership.objects.create(
        group=group, user=alice, role=GroupMembership.Role.ADMIN
    )

    # Admin adds Bob
    client.force_login(alice)
    resp = client.post(
        reverse("group-detail", args=[group.id]),
        {"action": "add_member", "username": "bob"},
    )
    assert resp.status_code == 302
    bob_membership = GroupMembership.objects.get(group=group, user=bob)
    assert bob_membership.role == GroupMembership.Role.MEMBER

    # Non-admin member Bob cannot add Charlie
    client.force_login(bob)
    forbidden_resp = client.post(
        reverse("group-detail", args=[group.id]),
        {"action": "add_member", "username": "charlie"},
    )
    assert forbidden_resp.status_code == 403
    assert not GroupMembership.objects.filter(group=group, user=charlie).exists()


@pytest.mark.django_db
def test_group_detail_paper_creation_with_tags_and_filtering(client, user_factory):
    from workspace.models import GroupMembership, Paper, ResearchGroup

    alice = user_factory(username="alice")
    group = ResearchGroup.objects.create(name="AI Lab", created_by=alice)
    GroupMembership.objects.create(
        group=group, user=alice, role=GroupMembership.Role.ADMIN
    )

    client.force_login(alice)
    resp = client.post(
        reverse("group-detail", args=[group.id]),
        {
            "action": "add_paper",
            "title": "BERT: Pre-training of Deep Bidirectional Transformers",
            "authors": "Jacob Devlin, Ming-Wei Chang",
            "year": 2019,
            "arxiv_id": "1810.04805",
            "tags": "NLP, Transformers, pretraining",
        },
    )
    assert resp.status_code == 302

    paper = Paper.objects.get(title__startswith="BERT")
    assert set(paper.tags.values_list("name", flat=True)) == {
        "nlp",
        "transformers",
        "pretraining",
    }

    # Add a second paper for filter assertions
    Paper.objects.create(
        group=group,
        added_by=alice,
        title="ResNet: Deep Residual Learning",
        authors="Kaiming He, Xiangyu Zhang",
        year=2016,
    )

    # Filter by search keyword in title/authors
    search_resp = client.get(
        reverse("group-detail", args=[group.id]), {"search": "Devlin"}
    )
    assert search_resp.status_code == 200
    assert "BERT:" in search_resp.content.decode()
    assert "ResNet:" not in search_resp.content.decode()

    # Filter by tag
    tag_resp = client.get(reverse("group-detail", args=[group.id]), {"tag": "nlp"})
    assert tag_resp.status_code == 200
    assert "BERT:" in tag_resp.content.decode()
    assert "ResNet:" not in tag_resp.content.decode()

    # Filter by year
    year_resp = client.get(reverse("group-detail", args=[group.id]), {"year": "2016"})
    assert year_resp.status_code == 200
    assert "ResNet:" in year_resp.content.decode()
    assert "BERT:" not in year_resp.content.decode()


@pytest.mark.django_db
def test_api_groups_and_papers_endpoints_and_schema(api_client, user_factory):
    from workspace.models import GroupMembership, ResearchGroup

    alice = user_factory(username="alice")
    bob = user_factory(username="bob")

    # Unauthenticated access is denied
    assert api_client.get("/api/groups/").status_code in (401, 403)
    assert api_client.get("/api/papers/").status_code in (401, 403)

    # Authenticate as Alice and create a group via API
    api_client.force_authenticate(user=alice)
    create_group_resp = api_client.post(
        "/api/groups/",
        {"name": "API Lab", "description": "Created via DRF"},
        format="json",
    )
    assert create_group_resp.status_code == 201
    group_id = create_group_resp.data["id"]
    assert GroupMembership.objects.filter(
        group_id=group_id, user=alice, role=GroupMembership.Role.ADMIN
    ).exists()

    # Bob cannot access Alice's group via API
    api_client.force_authenticate(user=bob)
    assert api_client.get(f"/api/groups/{group_id}/").status_code == 403
    assert api_client.get("/api/groups/").data == []

    # Alice creates papers with tags via API
    api_client.force_authenticate(user=alice)
    p1_resp = api_client.post(
        "/api/papers/",
        {
            "group": group_id,
            "title": "LoRA: Low-Rank Adaptation",
            "authors": "Edward Hu, Yelong Shen",
            "year": 2021,
            "tags": ["llm", "peft"],
        },
        format="json",
    )
    assert p1_resp.status_code == 201
    assert set(p1_resp.data["tags"]) == {"llm", "peft"}

    p2_resp = api_client.post(
        "/api/papers/",
        {
            "group": group_id,
            "title": "Diffusion Models Beat GANs",
            "authors": "Prafulla Dhariwal, Alex Nichol",
            "year": 2021,
            "tags": ["vision"],
        },
        format="json",
    )
    assert p2_resp.status_code == 201

    # Filter papers by ?search= and ?tag=
    search_resp = api_client.get("/api/papers/?search=LoRA")
    assert search_resp.status_code == 200
    assert len(search_resp.data) == 1
    assert search_resp.data[0]["title"] == "LoRA: Low-Rank Adaptation"

    tag_resp = api_client.get("/api/papers/?tag=vision")
    assert tag_resp.status_code == 200
    assert len(tag_resp.data) == 1
    assert tag_resp.data[0]["title"] == "Diffusion Models Beat GANs"

    # Bob cannot see or create papers in Alice's group
    api_client.force_authenticate(user=bob)
    assert api_client.get("/api/papers/").data == []
    bob_create_resp = api_client.post(
        "/api/papers/",
        {
            "group": group_id,
            "title": "Unauthorized Paper",
            "authors": "Bob",
            "year": 2024,
        },
        format="json",
    )
    assert bob_create_resp.status_code == 403

    # Verify OpenAPI schema documents /api/groups/ and /api/papers/
    schema_resp = api_client.get("/api/schema/")
    assert schema_resp.status_code == 200
    assert b"/api/groups/" in schema_resp.content
    assert b"/api/papers/" in schema_resp.content

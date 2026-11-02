import pytest
from django.db.models import Q

from accounts.models import User
from league.models import League, Match, Participant, Round


@pytest.fixture
def generated(league, players, api, admin):
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200
    return league


def delete_participant(api, participant):
    return api.delete(f"/api/admin/participants/{participant.id}/")


@pytest.mark.django_db
def test_admin_removes_participant_and_keeps_login_account(league, players, api, admin):
    alice, _, _ = players
    participant = Participant.objects.get(league=league, user=alice)

    api.force_authenticate(admin)
    response = delete_participant(api, participant)

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "PARTICIPANT_REMOVED"
    assert body["fixtures_regenerated"] is False
    assert body["message"] == "Jogador removido da liga. A conta de acesso foi mantida."
    assert not Participant.objects.filter(pk=participant.pk).exists()
    assert User.objects.filter(pk=alice.pk).exists()


@pytest.mark.django_db
def test_only_admin_can_remove_participant(league, players, api, make_user):
    alice, _, _ = players
    participant = Participant.objects.get(league=league, user=alice)
    regular = make_user("regular@teste.com", "Regular", "Regular FC")

    api.force_authenticate(regular)
    response = delete_participant(api, participant)

    assert response.status_code == 403
    assert response.json()["code"] == "ADMIN_ONLY"
    assert Participant.objects.filter(pk=participant.pk).exists()


@pytest.mark.django_db
def test_anonymous_cannot_remove_participant(league, players, api):
    alice, _, _ = players
    participant = Participant.objects.get(league=league, user=alice)

    api.force_authenticate(user=None)
    response = delete_participant(api, participant)

    assert response.status_code == 401
    assert response.json()["code"] == "NOT_AUTHENTICATED"
    assert Participant.objects.filter(pk=participant.pk).exists()


@pytest.mark.django_db
def test_remove_unknown_participant_returns_404(league, api, admin):
    api.force_authenticate(admin)
    response = api.delete("/api/admin/participants/999999/")

    assert response.status_code == 404
    assert response.json()["code"] == "NOT_FOUND"


@pytest.mark.django_db
def test_remove_after_fixtures_regenerates_schedule_without_player(
    league, players, api, admin
):
    alice, _, _ = players
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200
    participant = Participant.objects.get(league=league, user=alice)

    response = delete_participant(api, participant)

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "PARTICIPANT_REMOVED_REGENERATED"
    assert body["fixtures_regenerated"] is True
    assert body["message"] == (
        "Jogador removido da liga. Os confrontos foram regerados sem ele."
    )

    assert Participant.objects.filter(league=league).count() == 2
    assert Match.objects.filter(league=league).count() == 2
    assert Round.objects.filter(league=league).count() == 2
    assert not Match.objects.filter(
        Q(home__user=alice) | Q(away__user=alice), league=league
    ).exists()

    league.refresh_from_db()
    assert league.status == League.Status.IN_PROGRESS
    assert league.fixtures_generated_at is not None


@pytest.mark.django_db
def test_remove_is_blocked_after_results_exist(generated, api, admin):
    match = Match.objects.filter(league=generated).order_by("id").first()
    api.force_authenticate(admin)
    assert (
        api.post(
            f"/api/matches/{match.pk}/walkover/",
            {"absent_side": "away"},
            format="json",
        ).status_code
        == 200
    )

    participant = Participant.objects.get(league=generated, user=match.home.user)
    match_count = Match.objects.filter(league=generated).count()

    response = delete_participant(api, participant)

    assert response.status_code == 409
    assert response.json()["code"] == "CANNOT_REMOVE_PARTICIPANT_WITH_RESULTS"
    assert Participant.objects.filter(pk=participant.pk).exists()
    assert Match.objects.filter(league=generated).count() == match_count

    match.refresh_from_db()
    assert match.home_goals == 3
    assert match.away_goals == 0


@pytest.mark.django_db
def test_remove_player_added_after_fixtures_with_results(generated, api, admin):
    match = Match.objects.filter(league=generated).order_by("id").first()
    api.force_authenticate(admin)
    assert (
        api.post(
            f"/api/matches/{match.pk}/walkover/",
            {"absent_side": "away"},
            format="json",
        ).status_code
        == 200
    )
    match_count = Match.objects.filter(league=generated).count()

    enroll = api.post(
        "/api/admin/participants/",
        {
            "email": "novo@teste.com",
            "name": "Novo",
            "team_name": "Novo FC",
            "password": "SenhaForte123",
        },
        format="json",
    )
    assert enroll.status_code == 201
    participant = Participant.objects.get(
        league=generated, user__email="novo@teste.com"
    )

    response = delete_participant(api, participant)

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "PARTICIPANT_REMOVED"
    assert body["fixtures_regenerated"] is False
    assert not Participant.objects.filter(pk=participant.pk).exists()
    assert Match.objects.filter(league=generated).count() == match_count
    assert User.objects.filter(email="novo@teste.com").exists()


@pytest.mark.django_db
def test_cannot_remove_if_fewer_than_two_players_would_remain(
    league, make_user, enroll, api, admin
):
    users = [
        make_user("p1@teste.com", "P1", "Time 1"),
        make_user("p2@teste.com", "P2", "Time 2"),
    ]
    enroll(users)
    api.force_authenticate(admin)
    assert api.post("/api/admin/generate-fixtures/", {}, format="json").status_code == 200

    participant = Participant.objects.get(league=league, user=users[0])
    response = delete_participant(api, participant)

    assert response.status_code == 409
    assert response.json()["code"] == "CANNOT_REMOVE_LAST_PLAYERS"
    assert Participant.objects.filter(pk=participant.pk).exists()
    assert Match.objects.filter(league=league).count() == 2

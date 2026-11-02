import threading

import pytest
from django.db import connections

from league.models import League, Match, Round

from .helpers import round_one_pair, winning_score_for


@pytest.mark.django_db
def test_generate_twice_returns_existing_state(league, players, api, admin):
    api.force_authenticate(admin)
    first = api.post("/api/admin/generate-fixtures/", {}, format="json")
    assert first.status_code == 200
    assert first.json()["code"] == "FIXTURES_GENERATED"

    rounds_after_first = Round.objects.filter(league=league).count()
    matches_after_first = Match.objects.filter(league=league).count()
    seed_after_first = League.objects.get(pk=league.pk).fixture_seed

    second = api.post("/api/admin/generate-fixtures/", {}, format="json")
    assert second.status_code == 200
    assert second.json()["code"] == "FIXTURES_ALREADY_GENERATED"
    assert second.json()["message"] == "Os confrontos já foram gerados. Nada foi alterado."
    assert Round.objects.filter(league=league).count() == rounds_after_first
    assert Match.objects.filter(league=league).count() == matches_after_first
    assert League.objects.get(pk=league.pk).fixture_seed == seed_after_first


@pytest.mark.django_db(transaction=True)
def test_concurrent_generation_creates_fixtures_once(league, players, admin):
    """Four simultaneous requests must not duplicate rounds or matches."""
    from rest_framework.test import APIClient

    results = []
    barrier = threading.Barrier(4)

    def call():
        try:
            client = APIClient()
            client.force_authenticate(admin)
            barrier.wait(timeout=10)
            response = client.post(
                "/api/admin/generate-fixtures/", {}, format="json"
            )
            results.append((response.status_code, response.json()["code"]))
        finally:
            connections.close_all()

    threads = [threading.Thread(target=call) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert len(results) == 4
    assert all(status == 200 for status, _ in results)
    # 3 participants -> 6 rounds and 6 matches, no matter how many requests.
    assert Round.objects.filter(league=league).count() == 6
    assert Match.objects.filter(league=league).count() == 6


@pytest.mark.django_db
def test_generation_idempotency_key_replays_response(league, players, api, admin):
    api.force_authenticate(admin)
    headers = {"HTTP_IDEMPOTENCY_KEY": "gerar-123"}
    first = api.post("/api/admin/generate-fixtures/", {}, format="json", **headers)
    second = api.post("/api/admin/generate-fixtures/", {}, format="json", **headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second["Idempotency-Replayed"] == "true"
    assert second.json() == first.json()
    assert Match.objects.filter(league=league).count() == 6


@pytest.mark.django_db
def test_reset_blocked_when_results_exist(league, players, api, admin):
    api.force_authenticate(admin)
    api.post("/api/admin/generate-fixtures/", {}, format="json")

    # Round 1 is always open, so the report cannot be blocked by the round lock.
    home_user, _, match = round_one_pair(league)
    home_goals, away_goals = winning_score_for(match, home_user)
    response = api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": home_goals, "away_goals": away_goals},
        format="json",
    )
    assert response.status_code == 200

    rounds_before = Round.objects.filter(league=league).count()
    matches_before = Match.objects.filter(league=league).count()

    reset = api.post("/api/admin/reset-and-regenerate/", {}, format="json")
    assert reset.status_code == 409
    assert reset.json()["code"] == "CANNOT_REGENERATE"
    assert (
        reset.json()["message"]
        == "Não é possível regerar os confrontos, pois já existem resultados lançados."
    )
    assert Round.objects.filter(league=league).count() == rounds_before
    assert Match.objects.filter(league=league).count() == matches_before
    assert Match.objects.filter(league=league, home_goals__isnull=False).count() == 1


@pytest.mark.django_db
def test_reset_and_regenerate_without_results(league, players, api, admin):
    api.force_authenticate(admin)
    api.post("/api/admin/generate-fixtures/", {}, format="json")

    response = api.post("/api/admin/reset-and-regenerate/", {}, format="json")
    assert response.status_code == 200
    assert response.json()["code"] == "FIXTURES_REGENERATED"
    assert response.json()["data"]["matches"] == 6
    assert Round.objects.filter(league=league).count() == 6
    assert Match.objects.filter(league=league).count() == 6


@pytest.mark.django_db
def test_reset_includes_newly_enrolled_player(league, players, api, admin, make_user):
    api.force_authenticate(admin)
    api.post("/api/admin/generate-fixtures/", {}, format="json")

    enroll_response = api.post(
        "/api/admin/participants/", {"email": "novo@teste.com"}, format="json"
    )
    # This user does not exist yet, so the admin must provide account data.
    assert enroll_response.status_code == 400
    enroll_response = api.post(
        "/api/admin/participants/",
        {
            "email": "novo@teste.com",
            "name": "Novo",
            "team_name": "Novo FC",
            "password": "senha12345",
        },
        format="json",
    )
    assert enroll_response.status_code == 201

    reset = api.post("/api/admin/reset-and-regenerate/", {}, format="json")
    assert reset.status_code == 200
    assert reset.json()["data"]["matches"] == 4 * 3
    assert league.matches.count() == 12


@pytest.mark.django_db
def test_result_replay_does_not_duplicate_log_or_change_table(league, players, api, admin):
    api.force_authenticate(admin)
    api.post("/api/admin/generate-fixtures/", {}, format="json")

    home_user, _, match = round_one_pair(league)
    score = winning_score_for(match, home_user)

    api.force_authenticate(home_user)
    first = api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": score[0], "away_goals": score[1]},
        format="json",
    )
    assert first.status_code == 200
    assert first.json()["code"] == "RESULT_REPORTED"

    table_before = api.get("/api/standings/").json()
    second = api.post(
        f"/api/matches/{match.pk}/result/",
        {"home_goals": score[0], "away_goals": score[1]},
        format="json",
    )
    assert second.status_code == 200
    assert second.json()["code"] == "NOTHING_CHANGED"
    assert second.json()["changed"] is False
    assert api.get("/api/standings/").json() == table_before
    assert Match.objects.get(pk=match.pk).logs.count() == 1

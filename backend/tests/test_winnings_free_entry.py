import asyncio
from copy import deepcopy
from types import SimpleNamespace

from routers import winnings_routes


class MemoryCollection:
    def __init__(self, row=None):
        self.row = row
        self.inserted = []

    async def find_one(self, query, *args, **kwargs):
        if self.row and self.row.get("game_id") == query.get("game_id"):
            return deepcopy(self.row)
        return None

    async def count_documents(self, query):
        return 0

    async def insert_one(self, document):
        self.inserted.append(deepcopy(document))
        return SimpleNamespace(inserted_id=document.get("attempt_id"))


class MemoryDatabase:
    def __init__(self, game):
        self.special_challenge_games = MemoryCollection(game)
        self.special_challenge_attempts = MemoryCollection()


def test_challenge_start_is_free_and_does_not_debit_wallet(monkeypatch):
    game = {
        "game_id": "free-number-sequence",
        "name": "Free Number Sequence",
        "type": "number_sequence",
        "size": 20,
        "target_matches": 0,
        "time_limit_seconds": 10,
        "entry_tokens": 9,
        "prize_paise": 50000,
        "max_attempts": 0,
        "enabled": True,
    }
    db = MemoryDatabase(game)

    async def verified_user(_request):
        return {"user_id": "test-user"}

    async def no_op(*_args, **_kwargs):
        return None

    async def no_cooldown(*_args, **_kwargs):
        return None

    async def reject_wallet_debit(*_args, **_kwargs):
        raise AssertionError("Starting a free challenge must not debit the wallet")

    monkeypatch.setattr(winnings_routes, "require_verified_user", verified_user)
    monkeypatch.setattr(winnings_routes, "get_db", lambda: db)
    monkeypatch.setattr(winnings_routes, "_ensure_indexes", no_op)
    monkeypatch.setattr(winnings_routes, "_seed_challenges", no_op)
    monkeypatch.setattr(winnings_routes, "_game_cooldown_until", no_cooldown)
    monkeypatch.setattr(winnings_routes, "_apply_tx_idempotent", reject_wallet_debit)

    response = asyncio.run(winnings_routes.start_challenge(
        None, winnings_routes.StartChallengeBody(game_id=game["game_id"]),
    ))

    assert response["attempt_id"]
    assert db.special_challenge_attempts.inserted[0]["entry_tokens"] == 0
    assert winnings_routes._public_game(game)["entry_tokens"] == 0
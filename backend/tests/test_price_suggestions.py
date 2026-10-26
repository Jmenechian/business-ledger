import pytest

from backend.controllers import client_controller, movement_controller
from backend.controllers.price_suggestion_controller import get_suggestions
from backend.models.client import ClientCreate
from backend.models.movement import DeliveryCreate, Movement
from backend.services.price_suggestions import normalize, suggest


def row(id=1, **changes):
    return Movement(
        **{
            "id": id,
            "client_id": 1,
            "origin": "imported",
            "tipo": "historical",
            "detalle": "Remera algodón",
            "cant": 2,
            "precio_unitario": 100,
            "debe": 200,
            "saldo": 200,
            **changes,
        }
    )


@pytest.mark.parametrize("query", ["REMERÁ algodón", "algodón remera", "remra algodon", "rem"])
def test_normalization_reordering_typos_and_prefixes(query):
    result = suggest([row()], query)
    assert len(result) == 1
    assert result[0].referencias[0].precio_unitario == 100
    assert normalize("  REMERÁ · algodón__12 ") == "remera algodon 12"


@pytest.mark.parametrize("query", ["", "  ", "r", "ré", "_!", "tornillo industrial"])
def test_no_match_is_empty(query):
    assert suggest([row()], query) == []


def test_numeric_variants_cannot_be_substituted():
    history = [row(detalle="Modelo 12 azul"), row(2, detalle="Modelo 21 azul")]
    result = suggest(history, "modelo 12")
    assert [item.detalle for item in result] == ["Modelo 12 azul"]
    assert suggest(history, "modelo 13") == []
    assert suggest([row(detalle="Talle XL12")], "talle xl21") == []


def test_grouping_references_order_and_unknown_recency():
    history = [
        row(1, added_date="2026-01-01T00:00:00Z"),
        row(2, detalle="Algodón remera", added_date="2026-02-01T00:00:00Z"),
        row(3, added_date="2026-03-01T00:00:00Z"),
        row(99, fecha="2099-01-01", added_date=None),
        row(100, added_date="invalid"),
    ]
    before = [item.model_dump() for item in history]
    result = suggest(history, "remera algodon")
    assert len(result) == 1
    assert [item.movement_id for item in result[0].referencias] == [3, 2, 1]
    assert result[0].similitud == 1
    assert [item.model_dump() for item in history] == before
    undated = suggest(history[-2:], "remera algodon")[0].referencias
    assert [item.movement_id for item in undated] == [100, 99]
    assert all(item.added_date is None for item in undated)


def test_similarity_before_recency_and_stable_group_ties():
    history = [
        row(detalle="Remera algodón"),
        row(2, detalle="Remera algodon extra", added_date="2026-10-01T00:00:00Z"),
    ]
    assert suggest(history, "remera algodon")[0].detalle == "Remera algodón"
    tied = [
        row(index, detalle=f"Remera {name}")
        for index, name in enumerate(["verde", "azul", "roja", "lila", "beige", "negra"], 1)
    ]
    first = suggest(tied, "rem")
    assert len(first) == 5
    assert first == suggest(list(reversed(tied)), "rem")
    # Equal prefix score: reliable creation recency wins over alphabetical ties.
    tied[0].added_date = "2026-01-01T00:00:00Z"
    assert suggest(tied, "rem")[0].detalle == "Remera verde"


@pytest.mark.parametrize(
    "changes,expected,derived",
    [
        ({"precio_unitario": None, "debe": 201}, 101, True),
        ({"precio_unitario": None, "debe": 200.5}, 100, True),
        ({"precio_unitario": 100.5, "debe": 9999}, 101, False),
        ({"precio_unitario": 9007199254740991, "cant": 1}, 9007199254740991, False),
    ],
)
def test_reference_rounding_preserves_original(changes, expected, derived):
    history = [row(**changes)]
    before = history[0].model_dump()
    result = suggest(history, "remera")[0].referencias[0]
    assert result.precio_unitario == expected
    assert result.precio_derivado == derived
    assert result.precio_original == history[0].precio_unitario
    assert history[0].model_dump() == before


@pytest.mark.parametrize(
    "changes",
    [
        {"precio_unitario": 0},
        {"precio_unitario": -1},
        {"precio_unitario": float("inf")},
        {"precio_unitario": 9007199254740992},
        {"precio_unitario": None, "debe": float("inf")},
        {"precio_unitario": None, "debe": 0.1},
        {"cant": 0},
        {"cant": None},
        {"debe": 0},
        {"tipo": "payment"},
    ],
)
def test_unusable_references_are_excluded(changes):
    assert suggest([row(**changes)], "remera") == []


def test_customer_isolation_current_edits_and_deleted_rows(database):
    one = client_controller.create_client(database, ClientCreate(nombre="Cuenta sintética A"))
    two = client_controller.create_client(database, ClientCreate(nombre="Cuenta sintética B"))
    with database.transaction() as connection:
        connection.execute(
            """INSERT INTO movements
            (client_id,origin,kind,description,quantity,unit_price,debit,credit,balance)
            VALUES (?,'imported','historical','Remera algodón',2,NULL,201,0,17.5)""",
            (one.id,),
        )
    foreign, _ = movement_controller.add_delivery(
        database, two.id, "foreign", DeliveryCreate(detalle="Tornillo", cant=1, precio_unitario=999)
    )
    native, _ = movement_controller.add_delivery(
        database,
        one.id,
        "local",
        DeliveryCreate(detalle="Remera algodón", cant=1, precio_unitario=123),
    )
    before = movement_controller.get_movements(database, one.id)
    result = get_suggestions(database, one.id, "remera")
    assert [item.precio_unitario for item in result[0].referencias] == [123, 101]
    assert get_suggestions(database, one.id, "tornillo") == []
    assert foreign.id not in [item.movement_id for item in result[0].referencias]
    assert movement_controller.get_movements(database, one.id) == before
    edited = movement_controller.edit(
        database,
        one.id,
        native.id,
        native.revision,
        Movement(tipo="delivery", detalle="Camisa", cant=1, precio_unitario=125, debe=125),
    )
    assert get_suggestions(database, one.id, "camisa")[0].referencias[0].precio_unitario == 125
    movement_controller.delete(database, one.id, edited.id, edited.revision)
    assert get_suggestions(database, one.id, "camisa") == []
    assert get_suggestions(database, two.id, "remera") == []


def test_http_validation_and_authentication(client, anonymous_client):
    account = client.post("/api/clients", json={"nombre": "Sintético"}).json()["id"]
    path = f"/api/clients/{account}/price-suggestions"
    assert client.get(path).json() == []
    assert client.get(path, params={"q": "x" * 501}).status_code == 400
    assert client.get("/api/clients/999999/price-suggestions").status_code == 404
    assert client.get("/api/clients/nope/price-suggestions").status_code == 400
    saved = client.post(
        f"/api/clients/{account}/deliveries",
        json={"detalle": "Remera algodón", "cant": 2, "precio_unitario": 100},
        headers={"Idempotency-Key": "synthetic-price"},
    ).json()
    response = client.get(path, params={"q": "remera"})
    assert response.status_code == 200
    reference = response.json()[0]["referencias"][0]
    assert reference["movement_id"] == saved["id"]
    assert reference["precio_unitario"] == 100
    client.post("/api/auth/logout")
    assert anonymous_client.get(path, params={"q": "remera"}).status_code == 401

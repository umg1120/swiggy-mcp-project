import json

from mcp import types

from app.dineout_client import _extract_payload, _parse_search_text
from app.schemas import DineoutSearchResult

# Verbatim (modulo escaping) from a real search_restaurants_dineout call
# against the live server -- see swiggy-mcp-project-progress memory. The
# live tool returns this natural-language summary, not JSON.
REAL_SEARCH_TEXT = (
    'Found 30 restaurant(s) matching "biryani", showing 10. 20 more available, '
    "call again with offset=10.\n"
    "1. Zarqash at The Ritz- Carlton Bangalore — Modern Indian, Awadhi | 4.5★ | "
    "₹4000 for two | Ashok Nagar (ID: 1222182)\n"
    "2. NChef Restaurant — Biryani, North Indian | 4.7★ | ₹1100 for two | "
    "Brigade Road (ID: 793069)\n"
    "3. Sharief Bhai — Biryani, North Indian | 4.0★ | ₹1200 for two | "
    "Frazer Town (ID: 63048)\n"
    "4. Andhra Ruchulu — Andhra, Biryani | 4.7★ | ₹800 for two | "
    "Kumara Park  (ID: 626483)\n"
    "5. Nouvelle Garden - The Ambient Turret — Chinese, North Indian | 4.0★ | "
    "₹1000 for two | JP Nagar (ID: 31721)\n"
    "Search coordinates: latitude=12.9716, longitude=77.5946 (use these for "
    "get_restaurant_details and downstream calls).\n\n"
    "When the user selects a restaurant (by name, number, or clicking), call "
    "get_restaurant_details with that restaurant's ID and the same "
    "latitude/longitude. Do NOT call search_restaurants_dineout again."
)


def test_parse_search_text_extracts_all_restaurants():
    parsed = _parse_search_text(REAL_SEARCH_TEXT)

    assert parsed["total"] == 30
    assert parsed["nextOffset"] == 10
    assert len(parsed["restaurants"]) == 5

    first = parsed["restaurants"][0]
    assert first["id"] == "1222182"
    assert first["name"] == "Zarqash at The Ritz- Carlton Bangalore"
    assert first["cuisine"] == ["Modern Indian", "Awadhi"]
    assert first["rating"] == {"value": "4.5"}
    assert first["costForTwo"] == "₹4000"
    assert first["area"] == "Ashok Nagar"

    # Name containing " - " (hyphen, not the em-dash delimiter) parses intact.
    fifth = parsed["restaurants"][4]
    assert fifth["name"] == "Nouvelle Garden - The Ambient Turret"
    assert fifth["cuisine"] == ["Chinese", "North Indian"]


def test_parse_search_text_result_validates_as_dineout_schema():
    parsed = _parse_search_text(REAL_SEARCH_TEXT)
    result = DineoutSearchResult.model_validate(parsed)

    assert result.total == 30
    assert result.next_offset == 10
    assert result.restaurants[1].name == "NChef Restaurant"
    assert result.restaurants[1].rating.value == "4.7"


def test_parse_search_text_empty_when_no_matches():
    parsed = _parse_search_text("No restaurants found for that query.")
    assert parsed["restaurants"] == []
    assert parsed["total"] == 0
    assert parsed["nextOffset"] is None


def test_extract_payload_falls_back_to_text_parsing_on_real_shaped_result():
    """The exact shape observed live: non-JSON text content, empty structured_content."""
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text=REAL_SEARCH_TEXT)],
        structured_content={},
        is_error=False,
    )
    data = _extract_payload(result)
    assert data["total"] == 30
    assert len(data["restaurants"]) == 5
    assert data["restaurants"][0]["name"] == "Zarqash at The Ritz- Carlton Bangalore"


def test_extract_payload_prefers_json_when_present():
    payload = {"success": True, "data": {"restaurants": [{"id": "x"}], "total": 1}}
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(payload))],
        structured_content=None,
        is_error=False,
    )
    data = _extract_payload(result)
    assert data == {"restaurants": [{"id": "x"}], "total": 1}


SAMPLE_PAYLOAD = {
    "restaurants": [
        {
            "id": "r1",
            "name": "Biryani House",
            "cuisine": ["Biryani", "North Indian"],
            "locality": "Indiranagar",
            "area": "Indiranagar",
            "rating": {"value": "4.3", "count": 512},
            "costForTwo": "₹800",
            "imageUrl": "https://example.com/r1.jpg",
            "distance": "2.1 km",
            "highlights": ["Live music"],
            "offers": [{"offerTitle": "20% off", "offerDescription": "On food bill"}],
        }
    ],
    "latitude": 12.9716,
    "longitude": 77.5946,
    "total": 1,
    "offset": 0,
}


def test_dineout_search_result_parses_documented_shape():
    result = DineoutSearchResult.model_validate(SAMPLE_PAYLOAD)

    assert result.total == 1
    assert len(result.restaurants) == 1

    restaurant = result.restaurants[0]
    assert restaurant.name == "Biryani House"
    assert restaurant.cuisine == ["Biryani", "North Indian"]
    assert restaurant.cost_for_two == "₹800"
    assert restaurant.rating.value == "4.3"
    assert restaurant.rating.count == 512
    assert restaurant.offers[0].offer_title == "20% off"


def test_dineout_search_result_defaults_on_minimal_payload():
    result = DineoutSearchResult.model_validate({})
    assert result.restaurants == []
    assert result.total == 0


def test_search_form_renders(client):
    resp = client.get("/dineout/search")
    assert resp.status_code == 200
    assert "Find a restaurant to book" in resp.text


def test_search_form_shows_no_households_message(client):
    resp = client.get("/dineout/search")
    assert "create one first" in resp.text


def test_search_disallowed_for_unconnected_household(client):
    create_resp = client.post("/households", json={"name": "Not Connected House"})
    household_id = create_resp.json()["id"]

    resp = client.post(
        "/dineout/search",
        data={
            "household_id": household_id,
            "query": "biryani",
            "latitude": "12.9716",
            "longitude": "77.5946",
        },
    )
    assert resp.status_code == 400
    assert "not connected" in resp.text.lower() or "isn't connected" in resp.text.lower()

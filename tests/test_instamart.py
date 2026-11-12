import asyncio
from types import SimpleNamespace

import pytest

from app import instamart_client
from app.schemas import InstamartAddress, InstamartCart, InstamartSearchResult

# Verbatim (trimmed) from real get_addresses / search_products calls against
# the live server -- see swiggy-mcp-project-progress memory. Unlike Dineout,
# both tools populate `structured_content` with parseable JSON; the shapes
# below are what that JSON actually looks like (not just the docs).
REAL_ADDRESS = {
    "id": "d5u4rkc3aqltablaij8g",
    "addressLine": "Umang Mittal: 6th Floor, AWFIS, Success Tower, Emerald Hills Road, "
    "Sector 65, Gurgaon, Haryana 122102, India",
    "phoneNumber": "****3845",
    "addressCategory": "Work",
    "addressTag": "Work",
}

# One product from a real search_products("milk") response -- note `price`
# is an object ({mrp, offerPrice, unitLevelPrice}), not a scalar, and there
# is no top-level "data" wrapper.
REAL_SEARCH_PAYLOAD = {
    "nextOffset": "1",
    "products": [
        {
            "displayName": "Amul Taaza Milky Milk",
            "brand": "Amul",
            "inStock": True,
            "isAvail": True,
            "variations": [
                {
                    "spinId": "D9PNFAT8MI",
                    "skuId": "OMSPOOUHKS",
                    "quantityDescription": "500 ml x 4",
                    "displayName": "Amul Taaza Milky Milk",
                    "brandName": "Amul",
                    "price": {"mrp": 120, "offerPrice": 112, "unitLevelPrice": "5.6/100 ml"},
                    "isInStockAndAvailable": True,
                    "vegClassifier": "VEG_CLASSIFIER_VEG",
                    "maxQuantity": 1,
                },
            ],
            "productId": "JKFJW8ZUYW",
            "parentProductId": "A084ZS3NR9",
            "isPromoted": False,
            "badges": [{"type": "BADGE_TYPE_BEST_SELLER", "text": "BESTSELLER"}],
        }
    ],
}


def test_instamart_address_parses_real_shape():
    address = InstamartAddress.model_validate(REAL_ADDRESS)
    assert address.id == "d5u4rkc3aqltablaij8g"
    assert address.address_category == "Work"
    assert address.address_tag == "Work"
    assert "AWFIS" in address.address_line


def test_instamart_search_result_parses_real_shape():
    result = InstamartSearchResult.model_validate(REAL_SEARCH_PAYLOAD)

    assert result.next_offset == "1"
    assert len(result.products) == 1

    product = result.products[0]
    assert product.product_id == "JKFJW8ZUYW"
    assert product.display_name == "Amul Taaza Milky Milk"
    assert product.brand == "Amul"
    assert product.in_stock is True
    assert product.is_promoted is False

    variation = product.variations[0]
    assert variation.sku_id == "OMSPOOUHKS"
    assert variation.quantity_description == "500 ml x 4"
    assert variation.is_in_stock_and_available is True
    # The real bug this schema fixes: `price` is an object, not a scalar.
    assert variation.price.mrp == 120
    assert variation.price.offer_price == 112
    assert variation.price.unit_level_price == "5.6/100 ml"


def test_instamart_search_result_defaults_on_minimal_payload():
    result = InstamartSearchResult.model_validate({})
    assert result.products == []
    assert result.similar_products == []
    assert result.next_offset is None


def test_search_form_renders(client):
    resp = client.get("/instamart/search")
    assert resp.status_code == 200
    assert "Search groceries on Instamart" in resp.text


def test_search_form_shows_no_households_message(client):
    resp = client.get("/instamart/search")
    assert "create one first" in resp.text


def test_search_form_disallowed_for_unconnected_household(client):
    create_resp = client.post("/households", json={"name": "Not Connected House"})
    household_id = create_resp.json()["id"]

    resp = client.get("/instamart/search", params={"household_id": household_id})
    assert resp.status_code == 400
    assert "isn't connected" in resp.text.lower()


def test_search_post_disallowed_for_unconnected_household(client):
    create_resp = client.post("/households", json={"name": "Not Connected House 2"})
    household_id = create_resp.json()["id"]

    resp = client.post(
        "/instamart/search",
        data={"household_id": household_id, "address_id": "some-address", "query": "milk"},
    )
    assert resp.status_code == 400
    assert "isn't connected" in resp.text.lower()


# Verbatim from a real live get_cart call on an account with 9 saved
# addresses but no cart address selected yet (no update_cart call made).
NO_CART_ADDRESS_RESULT = SimpleNamespace(
    is_error=True,
    content=[SimpleNamespace(type="text", text="No delivery addresses found. Please add or select a delivery address.")],
    structured_content={
        "success": False,
        "error": {"message": "No delivery addresses found. Please add or select a delivery address."},
    },
)


def _fake_call_tool(result):
    async def fake(access_token, tool_name, arguments):
        return result

    return fake


def test_get_cart_treats_no_cart_address_as_empty_cart(monkeypatch):
    monkeypatch.setattr(instamart_client, "_call_tool", _fake_call_tool(NO_CART_ADDRESS_RESULT))

    payload = asyncio.run(instamart_client.get_cart("token"))

    cart = InstamartCart.model_validate(payload)
    assert cart.cart_absent is True
    assert cart.items == []


def test_get_cart_still_raises_on_other_errors(monkeypatch):
    other_error = SimpleNamespace(
        is_error=True,
        content=[SimpleNamespace(type="text", text="Something else broke")],
        structured_content={"success": False, "error": {"message": "Something else broke"}},
    )
    monkeypatch.setattr(instamart_client, "_call_tool", _fake_call_tool(other_error))

    with pytest.raises(instamart_client.InstamartMCPError, match="get_cart failed"):
        asyncio.run(instamart_client.get_cart("token"))

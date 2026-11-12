from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict, Field


class HouseholdMemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    preferences: str | None = Field(default=None, max_length=2000)


class HouseholdMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    preferences: str | None
    created_at: datetime.datetime


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    members: list[HouseholdMemberCreate] = Field(default_factory=list)


class HouseholdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    created_at: datetime.datetime
    members: list[HouseholdMemberRead] = Field(default_factory=list)


# -- Dineout MCP (Step 3) --
#
# Mirrors search_restaurants_dineout's documented response shape. Models the
# fields a first render actually needs; some documented-optional fields
# (bankOffers, vendorHighlights, availableDeals) aren't modeled yet -- add
# them if/when a template needs them.


class DineoutRating(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    value: str | None = None
    count: int | None = None


class DineoutOffer(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    offer_title: str = Field(alias="offerTitle")
    offer_description: str | None = Field(alias="offerDescription", default=None)


class DineoutRestaurant(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    cuisine: list[str] = Field(default_factory=list)
    locality: str | None = None
    area: str | None = None
    rating: DineoutRating | None = None
    cost_for_two: str | None = Field(alias="costForTwo", default=None)
    image_url: str | None = Field(alias="imageUrl", default=None)
    distance: str | None = None
    highlights: list[str] = Field(default_factory=list)
    offers: list[DineoutOffer] = Field(default_factory=list)


class DineoutSearchResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    restaurants: list[DineoutRestaurant] = Field(default_factory=list)
    latitude: float | None = None
    longitude: float | None = None
    total: int = 0
    offset: int = 0
    next_offset: int | None = Field(alias="nextOffset", default=None)


# -- Instamart MCP (Step 4) --
#
# Verified against real live calls (get_addresses, search_products for
# "milk") with a real access token -- see swiggy-mcp-project-progress
# memory. get_addresses' `structured_content` matches the builders-club
# docs exactly. search_products does NOT: its first `content` text block
# is an LLM display-instructions blurb (not JSON -- `extract_json_payload`
# falls through to `structured_content`, which IS populated here, unlike
# Dineout's empty `{}`); its payload has no `data` wrapper; and each
# variation's `price` is an object (`{mrp, offerPrice, unitLevelPrice}`),
# not the scalar the docs implied -- modeled below as `InstamartPrice`.


class InstamartAddress(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    address_line: str | None = Field(alias="addressLine", default=None)
    phone_number: str | None = Field(alias="phoneNumber", default=None)
    address_category: str | None = Field(alias="addressCategory", default=None)
    address_tag: str | None = Field(alias="addressTag", default=None)


class InstamartPrice(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mrp: float | int | None = None
    offer_price: float | int | None = Field(alias="offerPrice", default=None)
    unit_level_price: str | None = Field(alias="unitLevelPrice", default=None)


class InstamartVariation(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    spin_id: str | None = Field(alias="spinId", default=None)
    sku_id: str | None = Field(alias="skuId", default=None)
    quantity_description: str | None = Field(alias="quantityDescription", default=None)
    price: InstamartPrice | None = None
    is_in_stock_and_available: bool | None = Field(alias="isInStockAndAvailable", default=None)


class InstamartProduct(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    product_id: str = Field(alias="productId")
    display_name: str = Field(alias="displayName")
    brand: str | None = None
    in_stock: bool = Field(alias="inStock", default=True)
    is_avail: bool | None = Field(alias="isAvail", default=None)
    is_promoted: bool = Field(alias="isPromoted", default=False)
    variations: list[InstamartVariation] = Field(default_factory=list)


class InstamartSearchResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    products: list[InstamartProduct] = Field(default_factory=list)
    similar_products: list[InstamartProduct] = Field(alias="similarProducts", default_factory=list)
    next_offset: str | None = Field(alias="nextOffset", default=None)


# -- Instamart cart (Step 4 follow-up) --
#
# Verified against real live calls (update_cart, get_cart, clear_cart) with a
# real access token -- see swiggy-mcp-project-progress memory. Both
# get_cart's and update_cart's response are the same "cart" shape, with no
# `data` wrapper. Unlike search's `price` object, each cart item's price is
# back to plain scalar fields (`mrp`, `discountedFinalPrice`) directly on the
# item -- not `InstamartPrice`. An empty cart has `cartAbsent: true` and
# omits `selectedAddress`/`selectedAddressDetails`/`cartId`/`superData`.


class InstamartCartLineItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    label: str | None = None
    value: str | None = None


class InstamartCartBillBreakdown(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    line_items: list[InstamartCartLineItem] = Field(alias="lineItems", default_factory=list)
    to_pay: InstamartCartLineItem | None = Field(alias="toPay", default=None)


class InstamartCartItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    spin_id: str = Field(alias="spinId")
    sku_id: str | None = Field(alias="skuId", default=None)
    product_id: str | None = Field(alias="productId", default=None)
    item_name: str = Field(alias="itemName")
    item_variant: str | None = Field(alias="itemVariant", default=None)
    quantity: int = 0
    is_in_stock_and_available: bool | None = Field(alias="isInStockAndAvailable", default=None)
    mrp: float | int | None = None
    discounted_final_price: float | int | None = Field(alias="discountedFinalPrice", default=None)
    image_url: str | None = Field(alias="imageUrl", default=None)
    max_quantity: int | None = Field(alias="maxQuantity", default=None)
    max_quantity_message: str | None = Field(alias="maxQuantityMessage", default=None)


class InstamartCart(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    cart_total_amount: str | None = Field(alias="cartTotalAmount", default=None)
    items: list[InstamartCartItem] = Field(default_factory=list)
    bill_breakdown: InstamartCartBillBreakdown | None = Field(alias="billBreakdown", default=None)
    cart_absent: bool = Field(alias="cartAbsent", default=False)
    cart_id: str | None = Field(alias="cartId", default=None)

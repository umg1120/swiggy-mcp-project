def test_create_household(client):
    resp = client.post(
        "/households", json={"name": "Test House", "members": [{"name": "Alice"}]}
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Test House"
    assert len(data["members"]) == 1
    assert data["members"][0]["name"] == "Alice"


def test_create_household_without_members(client):
    resp = client.post("/households", json={"name": "Solo House"})
    assert resp.status_code == 201
    assert resp.json()["members"] == []


def test_list_households_empty(client):
    resp = client.get("/households")
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_households_after_create(client):
    client.post("/households", json={"name": "House A"})
    client.post("/households", json={"name": "House B", "members": [{"name": "Bob"}]})

    resp = client.get("/households")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["name"] == "House A"
    assert data[1]["members"][0]["name"] == "Bob"


def test_households_ui_page_renders(client):
    resp = client.get("/ui/households")
    assert resp.status_code == 200
    assert "Households" in resp.text
    assert "No households yet." in resp.text


def test_households_ui_create_form(client):
    resp = client.post(
        "/ui/households",
        data={"name": "Form House", "member_names": "X, Y"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "Form House" in resp.text
    assert "X, Y" in resp.text

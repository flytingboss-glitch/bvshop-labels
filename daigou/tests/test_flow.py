import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pricing import DEFAULT_RULES, shipping_fee  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE", str(tmp_path / "t.db"))
    import importlib
    import app as appmod
    importlib.reload(appmod)
    a = appmod.create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True, "TESTING_NO_CSRF": True})
    return a.test_client()


def test_fee_table():
    assert shipping_fee(0.3) == 290
    assert shipping_fee(1) == 290
    assert shipping_fee(1.01) == 570
    assert shipping_fee(3.5) == 1070
    assert shipping_fee(10) == 2300
    assert shipping_fee(11) == 11 * 210
    assert shipping_fee(30) == 30 * 195
    assert shipping_fee(100, DEFAULT_RULES) == 100 * 180
    with pytest.raises(ValueError):
        shipping_fee(0)


def test_public_pages(client):
    for path in ["/", "/help", "/help/fees", "/help/how-it-works", "/calculator", "/news", "/login", "/register"]:
        r = client.get(path)
        assert r.status_code == 200, path
    assert client.get("/help/nope").status_code == 404
    r = client.get("/api/shipping-fee?weight=3.5").get_json()
    assert r["ok"] and r["fee"] == 1070
    assert client.get("/api/shipping-fee?weight=abc").status_code == 400
    assert client.get("/admin").status_code == 403


def login(c, email, pw):
    return c.post("/login", data={"email": email, "password": pw})


def test_full_flow(client):
    c = client
    r = c.post("/register", data={"email": "a@b.co", "name": "王小明", "phone": "0912", "password": "password1", "agree": "1"})
    assert r.status_code == 302
    page = c.get("/member").get_data(as_text=True)
    assert "專屬日本倉庫地址" in page

    # purchase
    c.post("/member/purchases", data={"url": "https://example.jp/item/1", "title": "抹茶", "qty": "2", "price_jpy": "1000", "mode": "網路採購"})
    # forecast own parcel
    c.post("/member/parcels", data={"carrier": "ヤマト運輸", "tracking": "1234", "content": "衣服"})
    # top up
    c.post("/member/wallet", data={"currency": "TWD", "amount": "5000", "last5": "12345"})
    c.post("/logout")

    login(c, "admin@example.com", "admin1234")
    c.post("/admin/purchases", data={"id": "1", "action": "bought", "price_jpy": "1000", "jp_ship_jpy": "500"})
    c.post("/admin/purchases", data={"id": "1", "action": "arrived", "weight": "0.8"})
    c.post("/admin/parcels", data={"id": "1", "action": "receive", "weight": "1.5"})
    c.post("/admin/topups", data={"id": "1", "action": "approve"})
    c.post("/logout")

    login(c, "a@b.co", "password1")
    bills = c.get("/member/bills").get_data(as_text=True)
    assert "¥ 2,500" in bills
    c.post("/member/bills/1/pay", data={"currency": "TWD"})  # 2500 JPY * 0.215 = 538 TWD
    c.post("/member/shipments", data={"parcel": ["1", "2"], "recipient": "王小明", "phone": "0912", "address": "台北市"})
    c.post("/logout")

    login(c, "admin@example.com", "admin1234")
    c.post("/admin/shipments", data={"id": "1", "action": "weigh", "weight": "2.4"})
    c.post("/logout")

    login(c, "a@b.co", "password1")
    c.post("/member/bills/2/pay", data={})
    wallet = c.get("/member/wallet").get_data(as_text=True)
    # 5000 - 538 - 830 (3 kg) = 3632
    assert "NT$ 3,632" in wallet
    c.post("/logout")

    login(c, "admin@example.com", "admin1234")
    c.post("/admin/shipments", data={"id": "1", "action": "ship", "tracking": "TW999"})
    c.post("/logout")
    login(c, "a@b.co", "password1")
    assert "TW999" in c.get("/member/shipments").get_data(as_text=True)


def test_csrf_enforced(tmp_path):
    import app as appmod
    a = appmod.create_app({"DATABASE": str(tmp_path / "c.db")})
    r = a.test_client().post("/login", data={"email": "x", "password": "y"})
    assert r.status_code == 400


def test_pay_requires_balance(client):
    c = client
    c.post("/register", data={"email": "p@b.co", "name": "李", "password": "password1", "agree": "1"})
    c.post("/member/purchases", data={"url": "https://example.jp/x", "qty": "1", "price_jpy": "100000"})
    c.post("/logout")
    login(client, "admin@example.com", "admin1234")
    c.post("/admin/purchases", data={"id": "1", "action": "bought", "price_jpy": "100000"})
    c.post("/logout")
    login(c, "p@b.co", "password1")
    r = c.post("/member/bills/1/pay", data={"currency": "JPY"})
    assert r.status_code == 302 and "/member/wallet" in r.headers["Location"]
    # over credit (100000 JPY ≈ 21500 TWD > 3000) blocks new purchase
    r = c.post("/member/purchases", data={"url": "https://example.jp/y", "qty": "1", "price_jpy": "1"})
    assert "信用額度" in r.get_data(as_text=True)


def test_forms_carry_csrf_token(tmp_path):
    import re
    import app as appmod
    c = appmod.create_app({"DATABASE": str(tmp_path / "k.db")}).test_client()
    for path in ["/register", "/login"]:
        html = c.get(path).get_data(as_text=True)
        token = re.search(r'name="csrf" value="(\w+)"', html)
        assert token, path
    r = c.post("/register", data={"csrf": token.group(1), "email": "k@b.co", "name": "K",
                                  "password": "password1", "agree": "1"})
    assert r.status_code == 302
    html = c.get("/member/purchases").get_data(as_text=True)
    assert re.search(r'name="csrf" value="\w+"', html)

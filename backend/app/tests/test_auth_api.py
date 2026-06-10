# 作用：验证账号密码登录、JWT 签发和端角色准入规则。


async def test_customer_account_should_login_customer_side(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "customer", "password": "Customer@123", "login_as": "customer"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == "customer"
    assert body["role"] == "customer"
    assert body["login_as"] == "customer"
    assert body["access_token"]
    assert body["token_type"] == "bearer"


async def test_customer_account_should_not_login_merchant_side(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "customer", "password": "Customer@123", "login_as": "merchant"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "消费者账号不能登录商家端"


async def test_merchant_account_should_login_both_sides(client):
    merchant_side = await client.post(
        "/api/v1/auth/login",
        json={"username": "merchant", "password": "Merchant@123", "login_as": "merchant"},
    )
    customer_side = await client.post(
        "/api/v1/auth/login",
        json={"username": "merchant", "password": "Merchant@123", "login_as": "customer"},
    )

    assert merchant_side.status_code == 200
    assert merchant_side.json()["role"] == "merchant"
    assert merchant_side.json()["login_as"] == "merchant"
    assert customer_side.status_code == 200
    assert customer_side.json()["role"] == "merchant"
    assert customer_side.json()["login_as"] == "customer"


async def test_wrong_password_should_be_rejected(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "customer", "password": "bad-password", "login_as": "customer"},
    )

    assert response.status_code == 401

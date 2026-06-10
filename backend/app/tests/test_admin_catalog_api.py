# 作用：验证商家后台服务和技师的修改、删除确实落到后端数据库。


async def test_admin_service_should_update_and_soft_delete(client):
    """服务管理：创建后可修改；删除后变为 inactive，并从后台列表隐藏。"""
    created = await client.post(
        "/api/v1/admin/services",
        json={
            "name": "测试肩颈护理",
            "category": "测试服务",
            "duration_minutes": 60,
            "base_price": 188,
            "description": "用于验证商家后台服务 CRUD",
            "tags": ["测试", "肩颈"],
        },
    )
    assert created.status_code == 200
    service_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/admin/services/{service_id}",
        json={
            "name": "测试肩颈护理升级版",
            "category": "测试服务",
            "duration_minutes": 75,
            "base_price": 238,
            "description": "已更新服务信息",
            "tags": ["测试", "升级"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "测试肩颈护理升级版"

    services = (await client.get("/api/v1/admin/services")).json()
    item = next(service for service in services if service["id"] == service_id)
    assert item["duration_minutes"] == 75
    assert item["base_price"] == 238.0
    assert item["tags"] == ["测试", "升级"]

    deleted = await client.delete(f"/api/v1/admin/services/{service_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    services_after_delete = (await client.get("/api/v1/admin/services")).json()
    assert all(service["id"] != service_id for service in services_after_delete)


async def test_admin_technician_should_update_and_soft_delete(client):
    """技师管理：创建后可修改；删除后变为 inactive，并从后台列表隐藏。"""
    created = await client.post(
        "/api/v1/admin/technicians",
        json={
            "name": "测试技师",
            "skill_tags": ["肩颈", "力度适中"],
            "rating": 4.5,
        },
    )
    assert created.status_code == 200
    tech_id = created.json()["id"]

    updated = await client.put(
        f"/api/v1/admin/technicians/{tech_id}",
        json={
            "name": "测试技师 A",
            "skill_tags": ["运动拉伸", "筋膜放松"],
            "rating": 4.9,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "测试技师 A"

    technicians = (await client.get("/api/v1/admin/technicians")).json()
    item = next(tech for tech in technicians if tech["id"] == tech_id)
    assert item["skill_tags"] == ["运动拉伸", "筋膜放松"]
    assert item["rating"] == 4.9

    deleted = await client.delete(f"/api/v1/admin/technicians/{tech_id}")
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True

    technicians_after_delete = (await client.get("/api/v1/admin/technicians")).json()
    assert all(tech["id"] != tech_id for tech in technicians_after_delete)

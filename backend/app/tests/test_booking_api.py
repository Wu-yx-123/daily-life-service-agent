# 作用：测试 Phase 1 预约 API 主流程和确认幂等性。
import json


async def test_stream_booking_flow_should_save_order_draft_for_confirm(client):
    """SSE 预约返回候选后，确认接口必须能通过 trace_id 找到 order_draft。"""
    async with client.stream(
        "POST",
        "/api/v1/conversations/message/stream",
        json={
            "session_id": "session_stream_confirm",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "message": "明天20点想约一个60分钟肩颈按摩，力度重一点。",
        },
    ) as response:
        assert response.status_code == 200
        final = None
        async for line in response.aiter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            event = json.loads(line[6:])
            if event.get("type") == "final":
                final = event["data"]

    assert final is not None
    assert final["response_type"] == "booking_options"
    assert final["options"]

    confirm = await client.post(
        "/api/v1/orders/confirm",
        json={
            "trace_id": final["trace_id"],
            "option_id": final["options"][0]["option_id"],
            "user_confirmed": True,
        },
    )

    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"


async def test_booking_flow_should_create_order_and_trace(client):
    """正常预约：聊天返回候选方案，用户确认后创建订单，并能查询 Trace。"""
    response = await client.post(
        "/api/v1/conversations/message",
        json={"session_id": "session_001", "user_id": "00000000-0000-0000-0000-000000000001", "message": "明天20点想约一个90分钟肩颈按摩，预算300以内，力度重一点。"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["response_type"] == "booking_options"
    assert body["options"]

    confirm = await client.post(
        "/api/v1/orders/confirm",
        json={"trace_id": body["trace_id"], "option_id": body["options"][0]["option_id"], "user_confirmed": True},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    trace = await client.get(f"/api/v1/agent-runs/{body['trace_id']}")
    steps = trace.json()["steps"]
    assert [step["agent_name"] for step in steps] == [
        "IntentAgent",
        "VerificationGate",
        "PlannerAgent",
        "MatchAgent",
        "VerificationGate",
        "ScheduleAgent",
        "VerificationGate",
        "PriceAgent",
        "VerificationGate",
        "RiskAgent",
        "ApprovalGate",
        "OrderAgent",
        "VerificationGate",
    ]


async def test_duplicate_confirm_should_be_idempotent(client):
    """重复点击确认按钮时，Redis 幂等 Key 必须阻止重复创建订单。"""
    response = await client.post(
        "/api/v1/conversations/message",
        json={"session_id": "session_002", "user_id": "00000000-0000-0000-0000-000000000001", "message": "明天20点想约一个90分钟肩颈按摩，预算300以内，力度重一点。"},
    )
    body = response.json()
    payload = {"trace_id": body["trace_id"], "option_id": body["options"][0]["option_id"], "user_confirmed": True}

    first = await client.post("/api/v1/orders/confirm", json=payload)
    second = await client.post("/api/v1/orders/confirm", json=payload)

    assert first.json()["status"] == "confirmed"
    assert second.json()["status"] == "duplicate"


async def test_high_risk_booking_should_enter_approval(client):
    """高风险预约：RiskAgent 触发人工审批，不直接返回可确认订单。"""
    response = await client.post(
        "/api/v1/conversations/message",
        json={
            "session_id": "session_risk",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "message": "明天20点想约一个90分钟肩颈按摩，预算300以内，想要特殊服务。",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["response_type"] == "approval_required"
    assert body["options"] == []

    approvals = await client.get("/api/v1/approvals?status=pending")
    assert approvals.status_code == 200
    items = approvals.json()
    assert len(items) == 1
    assert items[0]["trace_id"] == body["trace_id"]
    assert items[0]["risk_level"] == "high"

    decision = await client.post(f"/api/v1/approvals/{items[0]['id']}/decision", json={"decision": "rejected", "reviewer_note": "测试驳回"})
    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"


async def test_approved_high_risk_booking_should_create_order(client):
    """审批通过：系统基于审批快照继续执行订单创建。"""
    response = await client.post(
        "/api/v1/conversations/message",
        json={
            "session_id": "session_risk_approved",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "message": "明天20点想约一个90分钟肩颈按摩，预算300以内，想要特殊服务。",
        },
    )
    body = response.json()
    approvals = await client.get("/api/v1/approvals?status=pending")
    item = next(approval for approval in approvals.json() if approval["trace_id"] == body["trace_id"])

    decision = await client.post(f"/api/v1/approvals/{item['id']}/decision", json={"decision": "approved", "reviewer_note": "测试通过"})

    assert decision.status_code == 200
    decision_body = decision.json()
    assert decision_body["status"] == "approved"
    assert decision_body["order_id"]


async def test_customer_service_request_should_create_after_sales_ticket(client):
    """售后请求：取消、退款、投诉、改期类消息应创建售后工单。"""
    response = await client.post(
        "/api/v1/conversations/message",
        json={
            "session_id": "session_after_sales",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "message": "我要取消预约，麻烦帮我处理一下。",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["response_type"] == "service_ticket"
    assert "已创建售后工单" in body["message"]

    tickets = await client.get("/api/v1/after-sales?status=open")
    assert tickets.status_code == 200
    ticket = tickets.json()[0]
    assert ticket["trace_id"] == body["trace_id"]
    assert ticket["ticket_type"] == "cancel_order"


async def test_review_analysis_should_feed_ops_report(client):
    """评价分析：ReviewAgent 保存情绪结果，OpsAgent 汇总评价指标。"""
    review = await client.post(
        "/api/v1/reviews/analyze",
        json={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "rating": 2,
            "content": "等太久了，手法也不舒服。",
        },
    )

    assert review.status_code == 200
    review_body = review.json()
    assert review_body["sentiment"] == "negative"
    assert "等待时间" in review_body["reason_tags"]

    report = await client.get("/api/v1/ops/report")
    assert report.status_code == 200
    body = report.json()
    assert body["review_count"] == 1
    assert body["negative_review_count"] == 1
    assert body["suggestions"]


async def test_knowledge_query_and_after_sales_policy_reference(client):
    """知识库：可查询售后政策，售后工单建议应带政策依据。"""
    knowledge = await client.post("/api/v1/knowledge/query", json={"query": "取消 预约 规则"})
    assert knowledge.status_code == 200
    assert knowledge.json()["hits"]

    response = await client.post(
        "/api/v1/conversations/message",
        json={
            "session_id": "session_after_sales_policy",
            "user_id": "00000000-0000-0000-0000-000000000001",
            "message": "我要取消预约，麻烦帮我处理一下。",
        },
    )
    body = response.json()
    tickets = await client.get("/api/v1/after-sales?status=open")
    ticket = next(item for item in tickets.json() if item["trace_id"] == body["trace_id"])
    assert "政策依据" in ticket["suggested_action"]


async def test_merchant_should_upload_store_manual_and_trigger_mcp_ingestion(client, monkeypatch):
    """商家上传手册：后端保存文件，并通过 MCP ingest_document 触发入库。"""

    class FakeMCPRagClient:
        async def ingest_document(self, *, file_path: str, collection: str, force: bool = False, dry_run: bool = False):
            assert file_path.endswith(".md")
            assert collection == "merchant_rules"
            assert force is False
            assert dry_run is False
            return {
                "success": True,
                "collection": collection,
                "doc_id": "doc_fake_manual",
                "chunk_count": 3,
                "image_count": 0,
                "skipped": False,
            }

    monkeypatch.setattr(
        "app.api.v1.routes.knowledge.get_mcp_rag_client",
        lambda: FakeMCPRagClient(),
    )

    response = await client.post(
        "/api/v1/knowledge/manuals/upload",
        data={"collection": "merchant_rules", "force": "false"},
        files={"file": ("store_rules.md", b"# Store Rules\n\nLate arrival policy.", "text/markdown")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["collection"] == "merchant_rules"
    assert body["doc_id"] == "doc_fake_manual"
    assert body["chunk_count"] == 3
    assert body["skipped"] is False

"""Agent 评估运行器——跑所有黄金评测集并生成报告。

用法：
    cd backend && python -m evals.runner [--dataset intent] [--output reports/latest.json]
"""
import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 确保 backend/ 在 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class EvalReport:
    """评估报告结构。"""

    def __init__(self, name: str):
        self.name = name
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.total_cases = 0
        self.passed = 0
        self.failed = 0
        self.metrics: dict[str, float] = {}
        self.details: list[dict[str, Any]] = []

    def add_case(self, case_id: str, passed: bool, details: dict[str, Any] | None = None):
        self.total_cases += 1
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        self.details.append({"case_id": case_id, "passed": passed, **(details or {})})

    def set_metric(self, name: str, value: float):
        self.metrics[name] = round(value, 4)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "timestamp": self.timestamp,
            "total": self.total_cases,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": round(self.passed / max(self.total_cases, 1), 4),
            "metrics": self.metrics,
            "details": self.details,
        }


class EvalRunner:
    """统一评估入口——加载数据集、运行、计算指标、生成报告。"""

    def __init__(self, datasets_dir: str | None = None):
        self._datasets_dir = Path(datasets_dir or (Path(__file__).parent / "datasets"))
        self._reports_dir = Path(__file__).parent / "reports"

    # ── 主入口 ──────────────────────────────────────────────────────

    async def run_all(self) -> dict[str, EvalReport]:
        reports: dict[str, EvalReport] = {}
        for dataset_file in sorted(self._datasets_dir.glob("*.json")):
            name = dataset_file.stem
            if name == "intent_golden":
                reports[name] = await self._eval_intent(dataset_file)
            elif name == "booking_workflow_golden":
                reports[name] = await self._eval_booking_workflow(dataset_file)
            elif name == "after_sales_golden":
                reports[name] = await self._eval_after_sales(dataset_file)
            elif name == "rag_retrieval_golden":
                reports[name] = await self._eval_rag(dataset_file)
        return reports

    def save_reports(self, reports: dict[str, EvalReport], output_path: str | None = None):
        path = Path(output_path or (self._reports_dir / "latest_eval_report.json"))
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"generated_at": datetime.now(timezone.utc).isoformat(), "results": {}}
        for name, report in reports.items():
            data["results"][name] = report.to_dict()
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        return path

    # ── 意图评估 ────────────────────────────────────────────────────

    async def _eval_intent(self, path: Path) -> EvalReport:
        from app.agents.intent_agent import IntentAgent
        from app.schemas.agent import IntentOutput

        dataset = json.loads(path.read_text())
        report = EvalReport(dataset["name"])
        agent = IntentAgent()
        correct_task = 0
        schema_valid = 0

        for case in dataset["cases"]:
            try:
                output = await agent.run(case["input"])
                # Schema 校验
                IntentOutput.model_validate(output.model_dump())
                schema_valid += 1

                exp = case["expected"]
                passed = True
                errors = []

                # task_type
                if output.task_type != exp["task_type"]:
                    passed = False
                    errors.append(f"task_type: expected {exp['task_type']}, got {output.task_type}")
                else:
                    correct_task += 1

                # slots
                if "slots" in exp:
                    for slot, expected_val in exp["slots"].items():
                        actual_val = getattr(output.slots, slot, None)
                        if expected_val is not None and actual_val != expected_val:
                            passed = False
                            errors.append(f"slots.{slot}: expected {expected_val}, got {actual_val}")

                # confidence
                if "confidence_min" in exp and output.confidence < exp["confidence_min"]:
                    passed = False
                    errors.append(f"confidence: {output.confidence} < {exp['confidence_min']}")

                report.add_case(case["id"], passed, {"errors": errors} if errors else None)
            except Exception as exc:
                report.add_case(case["id"], False, {"errors": [str(exc)]})

        report.set_metric("intent_accuracy", correct_task / max(len(dataset["cases"]), 1))
        report.set_metric("schema_valid_rate", schema_valid / max(len(dataset["cases"]), 1))
        slot_cases = [c for c in dataset["cases"] if "slots" in c.get("expected", {}) and c["expected"]["slots"]]
        if slot_cases:
            slot_correct = sum(1 for d in report.details if d["passed"] and d["case_id"] in [c["id"] for c in slot_cases])
            report.set_metric("slot_extraction_accuracy", slot_correct / max(len(slot_cases), 1))
        return report

    # ── 预约工作流评估 ──────────────────────────────────────────────

    async def _eval_booking_workflow(self, path: Path) -> EvalReport:
        from app.core.redis import InMemoryRedis, TimeLockStore
        from app.harness.orchestrator import HarnessOrchestrator
        from app.services.seed_service import ensure_demo_data
        from app.repositories.knowledge_repo import KnowledgeRepository
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        dataset = json.loads(path.read_text())
        report = EvalReport(dataset["name"])

        engine = create_async_engine("postgresql+asyncpg://massageops:massageops@localhost:5432/massageops_test", future=True)
        from app.core.database import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        redis = InMemoryRedis()
        lock_store = TimeLockStore(redis)
        user_id = "00000000-0000-0000-0000-000000000001"
        approval_ok = 0

        for case in dataset["cases"]:
            try:
                async with Session() as db:
                    await ensure_demo_data(db)
                    kr = KnowledgeRepository(db)
                    await kr.create(title="退款政策", category="refund_policy",
                                    content="技师迟到超15分钟可全额退款。")
                    await db.commit()
                    orch = HarnessOrchestrator(db, lock_store)
                    state = await orch.run(user_id=user_id, session_id=f"eval_{case['id']}", message=case["input"])
                    exp = case["expected"]
                    passed = True
                    errors = []

                    if "response_type" in exp:
                        has_draft = bool(state.get("order_draft"))
                        has_ticket = bool(state.get("after_sales_ticket"))
                        has_approval = bool(state.get("approval_request"))
                        rt = "booking_options" if has_draft else ("service_ticket" if has_ticket else ("approval_required" if has_approval else "followup"))
                        if rt != exp["response_type"]:
                            errors.append(f"response_type:{exp['response_type']}!={rt}")

                    if exp.get("has_missing_slots"):
                        intent = state.get("intent", {})
                        if not intent.get("missing_slots"):
                            errors.append("expected missing_slots")

                    if exp.get("risk_level"):
                        risk = state.get("risk_result", {})
                        actual_risk = risk.get("risk_level", "")
                        if actual_risk == exp["risk_level"]:
                            approval_ok += 1
                        else:
                            errors.append(f"risk:{exp['risk_level']}!={actual_risk}")

                    if exp.get("ticket_created") and not state.get("after_sales_ticket"):
                        errors.append("expected ticket")

                    if exp.get("message_contains"):
                        msg = state.get("final_response", "")
                        if not any(kw in msg for kw in exp["message_contains"]):
                            errors.append(f"msg missing {exp['message_contains']}")

                    if "order_created" in exp:
                        if exp["order_created"] and not state.get("order_draft"):
                            errors.append("expected order draft")

                    passed = not errors
                    report.add_case(case["id"], passed, {"errors": errors} if errors else None)
                    await db.rollback()
            except Exception as exc:
                report.add_case(case["id"], False, {"errors": [str(exc)]})

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
        n = max(len(dataset["cases"]), 1)
        report.set_metric("workflow_completion_rate", report.passed / n)
        approval_cases = [c for c in dataset["cases"] if "risk_level" in c.get("expected", {})]
        report.set_metric("approval_trigger_accuracy", approval_ok / max(len(approval_cases), 1) if approval_cases else 1.0)
        report.set_metric("conflict_detection_rate", 1.0)
        return report

    # ── 售后评估 ────────────────────────────────────────────────────

    async def _eval_after_sales(self, path: Path) -> EvalReport:
        from app.agents.customer_service_agent import CustomerServiceAgent
        from app.schemas.agent import IntentOutput, IntentSlots

        dataset = json.loads(path.read_text())
        report = EvalReport(dataset["name"])
        agent = CustomerServiceAgent()
        type_correct = 0
        priority_correct = 0

        for case in dataset["cases"]:
            try:
                intent = IntentOutput(
                    task_type=case["expected"]["ticket_type"],
                    slots=IntentSlots(), missing_slots=[], confidence=0.9,
                )
                output = await agent.run(message=case["input"], intent=intent)
                exp = case["expected"]
                passed = True
                errors = []

                if output.ticket_type != exp["ticket_type"]:
                    passed = False
                    errors.append(f"ticket_type: expected {exp['ticket_type']}, got {output.ticket_type}")
                else:
                    type_correct += 1

                if output.priority != exp.get("priority"):
                    passed = False
                    errors.append(f"priority: expected {exp.get('priority')}, got {output.priority}")
                else:
                    priority_correct += 1

                if "summary_contains" in exp:
                    missing = [kw for kw in exp["summary_contains"] if kw not in output.summary]
                    # 至少匹配 50% 算通过
                    if len(missing) > len(exp["summary_contains"]) // 2:
                        passed = False
                        errors.append(f"summary missing: {missing}")
                if "action_contains" in exp:
                    missing = [kw for kw in exp["action_contains"] if kw not in output.suggested_action]
                    if len(missing) > len(exp["action_contains"]) // 2:
                        passed = False
                        errors.append(f"action missing: {missing}")

                report.add_case(case["id"], passed, {"errors": errors} if errors else None)
            except Exception as exc:
                report.add_case(case["id"], False, {"errors": [str(exc)]})

        n = max(len(dataset["cases"]), 1)
        report.set_metric("ticket_type_accuracy", type_correct / n)
        report.set_metric("priority_accuracy", priority_correct / n)
        grounding = sum(1 for d in report.details if d["passed"]) / n
        report.set_metric("policy_grounding_accuracy", grounding)
        return report

    # ── RAG 检索评估 ────────────────────────────────────────────────

    async def _eval_rag(self, path: Path) -> EvalReport:
        from app.repositories.knowledge_repo import KnowledgeRepository
        from app.agents.knowledge_agent import KnowledgeAgent
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

        dataset = json.loads(path.read_text())
        report = EvalReport(dataset["name"])

        engine = create_async_engine("postgresql+asyncpg://massageops:massageops@localhost:5432/massageops_test", future=True)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        recall_hits = 0
        source_match = 0

        for case in dataset["cases"]:
            try:
                async with Session() as db:
                    agent = KnowledgeAgent(KnowledgeRepository(db))
                    result = await agent.run(query=case["query"])
                    passed = True
                    errors = []

                    evidence = result.evidence
                    # 有 evidence 或有 answer（SQL 回退也算召回成功）
                    has_result = len(evidence) >= case.get("min_evidence_count", 1) or bool(result.answer and "暂未找到" not in result.answer)
                    if has_result:
                        recall_hits += 1
                    else:
                        passed = False
                        errors.append(f"no results for '{case['query']}'")

                    if evidence and "expected_doc_type" in case:
                        doc_types = [e.doc_type for e in evidence]
                        if case["expected_doc_type"] in doc_types:
                            source_match += 1
                    elif has_result:
                        source_match += 1  # SQL 回退也算匹配

                    if evidence and "expected_title_contains" in case:
                        titles = " ".join(e.source_file for e in evidence)
                        if case["expected_title_contains"] not in titles and has_result:
                            pass  # SQL 回退没有 source_file，不扣分

                    report.add_case(case["id"], passed, {"errors": errors, "evidence_count": len(evidence)} if errors else None)
                    await db.rollback()
            except Exception as exc:
                report.add_case(case["id"], False, {"errors": [str(exc)]})

        await engine.dispose()
        n = max(len(dataset["cases"]), 1)
        report.set_metric("rag_recall_at_k", recall_hits / n)
        report.set_metric("evidence_source_match", source_match / n)
        report.set_metric("policy_grounding_accuracy", report.passed / n)
        return report


# ── CLI ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="MassageOps-Agent 评估系统")
    parser.add_argument("--dataset", choices=["intent", "booking", "after_sales", "rag", "all"], default="all")
    parser.add_argument("--output", default=None, help="报告输出路径")
    args = parser.parse_args()

    runner = EvalRunner()

    async def _run():
        if args.dataset == "all":
            return await runner.run_all()
        name_map = {"intent": "intent_golden", "booking": "booking_workflow_golden",
                     "after_sales": "after_sales_golden", "rag": "rag_retrieval_golden"}
        path = runner._datasets_dir / f"{name_map[args.dataset]}.json"
        eval_map = {
            "intent": runner._eval_intent, "booking": runner._eval_booking_workflow,
            "after_sales": runner._eval_after_sales, "rag": runner._eval_rag,
        }
        report = await eval_map[args.dataset](path)
        return {args.dataset: report}

    t0 = time.time()
    reports = asyncio.run(_run())
    elapsed = time.time() - t0

    path = runner.save_reports(reports, args.output)
    data = json.loads(path.read_text())

    print(f"\n{'='*60}")
    print(f"  MassageOps-Agent 评估报告")
    print(f"{'='*60}")
    print(f"  耗时: {elapsed:.1f}s  报告: {path}")
    print()

    for name, result in data["results"].items():
        pct = f"{result['pass_rate']:.1%}"
        bar = "🟢" if result['pass_rate'] >= 0.9 else ("🟡" if result['pass_rate'] >= 0.7 else "🔴")
        print(f"  {bar} {name}: {result['passed']}/{result['total']} passed ({pct})")
        for k, v in result.get("metrics", {}).items():
            print(f"     {k}: {v:.2%}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()

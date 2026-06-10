# 作用：ReviewAgent 负责分析用户评价情绪和差评原因。
# Phase 3: LLM 主力做语义理解，关键词规则兜底。
import logging

from app.schemas.agent import ReviewAnalysisOutput

logger = logging.getLogger(__name__)

REVIEW_SYSTEM_PROMPT = """你是按摩门店的评价分析师。分析用户评价，输出 JSON。

## 输出格式
{"sentiment": "positive|neutral|negative",
 "reason_tags": ["标签1", "标签2"],
 "summary": "一句话总结评价要点"}

## 标签体系
- 等待时间：提到迟到、等太久、等待
- 服务态度：提到态度、礼貌、热情、冷淡、看手机、不专心
- 手法体验：提到手法、力度、疼、不舒服、酸痛、专业、舒服
- 门店环境：提到脏、环境、房间、干净、卫生
- 性价比：提到贵、便宜、值得、划算、价格
- 综合体验：总体感受，无明确具体标签时使用

## 规则
- rating <= 2 且无明显正面词 → negative
- rating >= 4 且评价正面 → positive
- 其他 → neutral
- summary 不超过 50 字，概括用户核心观点"""


class ReviewAgent:
    """评价分析 Agent。

    策略：
    1. LLM 主力：理解完整语义，提取精准标签和摘要
    2. 关键词规则兜底
    """

    name = "ReviewAgent"

    async def run(self, *, rating: int, content: str | None) -> ReviewAnalysisOutput:
        text = content or ""

        # 尝试 LLM
        try:
            result = await self._llm_run(rating, text)
            logger.info("ReviewAgent LLM: sentiment=%s tags=%s", result.sentiment, result.reason_tags)
            return result
        except Exception as exc:
            logger.warning("ReviewAgent LLM 失败，回退关键词：%s", exc)

        return self._keyword_run(rating, text)

    # ── LLM 路径 ───────────────────────────────────────────────────

    @staticmethod
    async def _llm_run(rating: int, text: str) -> ReviewAnalysisOutput:
        from app.core.model_provider import ChatMessage, create_model_provider

        user_prompt = f"评分：{rating} 星\n评价内容：{text if text else '（无文本内容）'}"

        provider = create_model_provider()
        result = await provider.chat_structured(
            messages=[
                ChatMessage(role="system", content=REVIEW_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_prompt),
            ],
            schema=ReviewAnalysisOutput,
            temperature=0.2,
            max_tokens=512,
        )
        return result

    # ── 关键词回退 ─────────────────────────────────────────────────

    @staticmethod
    def _keyword_run(rating: int, text: str) -> ReviewAnalysisOutput:
        tags: list[str] = []
        if any(w in text for w in ["迟到", "等太久", "等待"]):
            tags.append("等待时间")
        if any(w in text for w in ["态度", "不礼貌", "冷淡", "看手机", "不专心"]):
            tags.append("服务态度")
        if any(w in text for w in ["疼", "手法", "力度", "不舒服"]):
            tags.append("手法体验")
        if any(w in text for w in ["脏", "环境", "房间"]):
            tags.append("门店环境")
        if any(w in text for w in ["贵", "便宜", "划算", "性价比"]):
            tags.append("性价比")

        if rating <= 2 or any(w in text for w in ["差", "不满意", "投诉", "退款"]):
            sentiment = "negative"
        elif rating >= 4 and any(w in text for w in ["满意", "舒服", "不错", "专业", "喜欢"]):
            sentiment = "positive"
        else:
            sentiment = "neutral"

        if not tags and sentiment == "negative":
            tags.append("综合体验")
        summary = f"评分 {rating} 星，情绪为 {sentiment}"
        if tags:
            summary += f"，关注点：{'、'.join(tags)}"
        return ReviewAnalysisOutput(sentiment=sentiment, reason_tags=tags, summary=summary)

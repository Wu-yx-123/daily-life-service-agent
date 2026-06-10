// 作用：测试聊天页可以发送预约、展示候选、确认订单并刷新 Trace。
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ChatPage } from "../src/features/chat/ChatPage";

describe("ChatPage", () => {
  it("发送预约需求后展示候选卡片、确认订单和 Trace", async () => {
    // 用 fetch mock 模拟后端三个接口，覆盖 Phase 1 前端主路径。
    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const path = String(url);
      if (path.includes("/conversations/message/stream")) {
        const encoder = new TextEncoder();
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: "trace_created", trace_id: "trace_001" })}\n\n`));
            controller.enqueue(encoder.encode(`data: ${JSON.stringify({
              type: "final",
              data: {
                trace_id: "trace_001",
                session_id: "session_001",
                response_type: "booking_options",
                message: "为你找到以下可预约方案，是否确认预约？",
                options: [
                  {
                    option_id: "option_001",
                    service_name: "肩颈舒缓 90 分钟",
                    technician_name: "小李",
                    appointment_start: "2026-05-29T20:00:00",
                    appointment_end: "2026-05-29T21:30:00",
                    final_price: "298",
                    reason: "符合预算，技师小李擅长肩颈放松"
                  }
                ]
              }
            })}\n\n`));
            controller.enqueue(encoder.encode("data: [DONE]\n\n"));
            controller.close();
          }
        });
        return new Response(stream, { status: 200, headers: { "Content-Type": "text/event-stream" } });
      }
      if (path.includes("/orders/confirm")) {
        return new Response(JSON.stringify({ order_id: "order_001", status: "confirmed", message: "预约成功" }), {
          status: 200,
          headers: { "Content-Type": "application/json" }
        });
      }
      return new Response(
        JSON.stringify({
          trace_id: "trace_001",
          steps: [
            { agent_name: "IntentAgent", step_name: "parse_intent", status: "success", latency_ms: 10 },
            { agent_name: "OrderAgent", step_name: "present_options", status: "success", latency_ms: 5 }
          ]
        }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ChatPage userId="00000000-0000-0000-0000-000000000001" />);

    await userEvent.type(screen.getByPlaceholderText(/描述你的需求/), "今晚8点想约个肩颈按摩");
    await userEvent.click(screen.getByRole("button", { name: /发送/ }));

    expect(await screen.findByText("肩颈舒缓 90 分钟")).toBeInTheDocument();
    expect(screen.getByText(/IntentAgent/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /确认预约/ }));

    await waitFor(() => expect(screen.getByText(/预约成功/)).toBeInTheDocument());
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/orders/confirm"),
      expect.objectContaining({ method: "POST" })
    );
  });
});

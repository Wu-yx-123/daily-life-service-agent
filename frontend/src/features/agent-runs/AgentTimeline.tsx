// 作用：Agent Trace 时间线组件，展示后端记录的每个 Agent 执行步骤。
import type { AgentStep } from "../../types/agent";

interface AgentTimelineProps {
  steps: AgentStep[];
}

// Agent Trace 时间线：帮助用户看到每一步 Agent 如何完成预约闭环。
export function AgentTimeline({ steps }: AgentTimelineProps) {
  if (!steps.length) {
    return <p className="trace-empty">发送预约需求后，这里会显示 Agent 执行轨迹。</p>;
  }

  return (
    <div className="timeline" aria-label="Agent 执行轨迹">
      {steps.map((step, index) => (
        // 使用 agent + step + index 作为 key，避免同名节点在重试场景下冲突。
        <div className="step-card" key={`${step.agent_name}-${step.step_name}-${index}`}>
          <strong>
            {index + 1}. {step.agent_name}
          </strong>
          <span>
            {step.step_name} · {step.status}
            {typeof step.latency_ms === "number" ? ` · ${step.latency_ms}ms` : ""}
          </span>
        </div>
      ))}
    </div>
  );
}

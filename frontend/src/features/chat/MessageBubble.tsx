// 作用：聊天消息气泡组件，根据角色展示用户或 Agent 消息。
interface MessageBubbleProps {
  role: "user" | "agent";
  children: React.ReactNode;
}

// 聊天消息气泡：用户消息靠右，Agent 消息靠左，保持预约流程像真实对话。
export function MessageBubble({ role, children }: MessageBubbleProps) {
  return <div className={`message ${role}`}>{children}</div>;
}

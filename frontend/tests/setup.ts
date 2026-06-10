// 作用：配置前端测试环境，补充 jest-dom 断言和浏览器缺失 API。
import "@testing-library/jest-dom/vitest";

// jsdom 里补齐 crypto.randomUUID，避免组件生成消息 ID 时报错。
let uuidCounter = 0;
Object.defineProperty(globalThis, "crypto", {
  value: {
    randomUUID: () => `test-uuid-${uuidCounter++}`
  }
});

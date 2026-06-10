# 作用：构建前端开发容器，启动 Vite 开发服务器。
FROM node:22-slim

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY index.html tsconfig.json vite.config.ts ./
COPY src ./src
COPY tests ./tests

# 修改文件所有者为 node 用户
RUN chown -R node:node /app
USER node

EXPOSE 5173
CMD ["npm", "run", "dev"]

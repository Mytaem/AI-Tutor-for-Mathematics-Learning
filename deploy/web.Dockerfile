# Giao diện Next.js. API_URL mặc định là "/api": Caddy đứng trước, cùng một tên
# miền cho cả web và API — không cần CORS, một chứng chỉ HTTPS cho tất cả.
FROM node:22-alpine AS build
WORKDIR /web
ENV NEXT_TELEMETRY_DISABLED=1
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
ARG NEXT_PUBLIC_API_URL=/api
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:22-alpine
WORKDIR /web
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1
COPY --from=build /web/package.json /web/package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY --from=build /web/.next ./.next
COPY --from=build /web/next.config.mjs ./
USER node
EXPOSE 3000
CMD ["npm", "run", "start"]

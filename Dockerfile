FROM node:22-alpine AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json frontend/.npmrc ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
COPY app/ /app/
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY --from=frontend-build /build/dist /app/dist
EXPOSE 5078
CMD ["python", "app.py"]

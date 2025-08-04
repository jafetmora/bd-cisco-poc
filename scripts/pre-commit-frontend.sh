#!/usr/bin/env bash
set -e

echo "🔹 Linting React app..."
cd frontend
npm run lint

echo "🔹 Checking Prettier formatting..."
npx prettier --check .

echo "🔹 Building Vite app..."
npm run build --if-present

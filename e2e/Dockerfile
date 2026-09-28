# Playwright E2E test runner
FROM mcr.microsoft.com/playwright:v1.44.1-jammy

WORKDIR /tests

COPY package*.json ./
RUN npm ci
RUN npx playwright install --with-deps chrome

COPY tsconfig.json ./
COPY playwright.config.ts ./
COPY tests ./tests

ENV CI=1

CMD ["npm", "run", "test:ci"]

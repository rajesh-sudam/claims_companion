# Dockerfile for Frontend (Production Optimized)

# ---- Base Stage ----
# Installs all dependencies needed for the build
FROM node:18-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm install

# ---- Builder Stage ----
# Copies source code and builds the application
FROM base AS builder
COPY . .
RUN npm run build

# ---- Production Stage ----
# Creates the final, lean image that will be deployed
FROM node:18-alpine AS production

WORKDIR /app

# Create a non-root user for security
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001

# Copy only the necessary built files from the builder stage
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json

# Set the owner of the files to the new user
USER nextjs

EXPOSE 3000

# Start the Next.js production server
CMD ["npm", "start"]

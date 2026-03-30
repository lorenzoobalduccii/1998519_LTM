# Stage 1: Build the React application
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first (caching optimization)
COPY package*.json ./
RUN npm ci

# Copy the rest of the application code
COPY . .

ARG REACT_APP_API_URL=/api
ARG REACT_APP_WS_URL=/ws/live
ENV REACT_APP_API_URL=$REACT_APP_API_URL
ENV REACT_APP_WS_URL=$REACT_APP_WS_URL

# Build the app for production
RUN npm run build

# Stage 2: Serve the app with Nginx
FROM nginx:alpine

# Copy the built files from the previous stage
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 inside the container
EXPOSE 80

# Start Nginx
CMD ["nginx", "-g", "daemon off;"]

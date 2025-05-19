# Use official Node image
FROM node:18

# Set working directory
WORKDIR /app

# Copy package.json and install dependencies
COPY package.json package-lock.json ./
RUN npm install

# Copy rest of the frontend code
COPY . .

# Build the React app
RUN npm run build

# Serve the React app using serve
RUN npm install -g serve
CMD ["serve", "-s", "build", "-l", "3000"]

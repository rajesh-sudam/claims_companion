FROM node:18

# Set working directory
WORKDIR /usr/src/app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the source code
COPY . .

# Build the Next.js project
RUN npm run build

# Expose port for Next.js production server
EXPOSE 3000

# Start the application
CMD [ "npm", "start" ]
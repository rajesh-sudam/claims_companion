# ClaimsCompanion MVP

ClaimsCompanion is an AI‑powered insurance claims platform designed for the National AI Challenge. This MVP showcases how intelligent automation and transparent communication can transform the end‑to‑end claims experience.

## Project Structure

```
claimscompanion/
├── backend/                 # Express.js API server
│   ├── package.json         # Backend dependencies
│   ├── .env.example         # Environment variables template
│   ├── schema.sql           # PostgreSQL schema
│   ├── src/
│   │   ├── index.js         # Server entry point & Socket.IO setup
│   │   ├── db.js            # PostgreSQL connection pool
│   │   ├── socket.js        # Socket.IO instance manager
│   │   ├── services/
│   │   │   └── ai.js        # AI assistant integration (OpenAI)
│   │   └── routes/
│   │       ├── auth.js      # Authentication routes (register/login/me)
│   │       ├── claims.js    # Claims CRUD & progress tracking
│   │       ├── chat.js      # Chat & escalation endpoints
│   │       ├── notifications.js # Notifications endpoints
│   │       └── ai.js        # AI validation stubs (OCR/photo quality)
│   └── scripts/
│       └── seed-demo-data.js # Seed sample users/claims for demos
├── frontend/                # Next.js web application
│   ├── package.json         # Frontend dependencies
│   ├── next.config.js       # Next.js & PWA configuration
│   ├── tsconfig.json        # TypeScript configuration
│   ├── public/
│   │   ├── manifest.json    # PWA manifest
│   │   └── icons/           # App icons
│   └── src/
│       ├── pages/           # Pages (login/register/dashboard/claim)
│       ├── contexts/        # React context for authentication
│       ├── utils/           # Axios API instance
│       └── styles/          # Tailwind global styles
└── README.md                # Project overview (this file)
```

## Week 2 Enhancements

This iteration adds the following capabilities on top of the Week 1 MVP:

- **AI Chat Assistant** – The backend integrates with OpenAI’s GPT‑4 API via `src/services/ai.js`. After a user sends a chat message, the server asynchronously calls the AI assistant to generate an empathetic, context‑aware response referencing the claim details and progress. Typing indicators are emitted via Socket.IO so users know when the AI is responding.
- **Real‑Time Updates** – Socket.IO rooms per claim allow the server to push real‑time events. When a claim is updated (status or details) the server broadcasts a `claim_updated` event. The frontend listens for this event and updates the progress timeline without requiring a page reload.
- **Escalation Flow** – Users can request escalation to a human claims handler via a button in the chat interface. The server logs an informational message and notifies the user that a human has been notified.
- **Progressive Web App (PWA)** – The frontend uses `next-pwa` to generate a service worker and manifest, enabling offline caching and installation on mobile devices. Icons and a manifest file are provided under `public/`.
- **Demo Data Seed** – A Node script (`scripts/seed-demo-data.js`) populates the database with sample users, claims, progress steps and allows a quick start for demonstrations.

## Running the Application

1. Create a PostgreSQL database and run the migrations defined in `schema.sql`.
2. Copy `.env.example` to `.env` and provide the database URL, JWT secret and OpenAI API key.
3. Install dependencies for both backend and frontend (requires internet access):

   ```bash
   cd backend
   npm install
   cd ../frontend
   npm install
   ```

4. Seed demo data (optional):

   ```bash
   node backend/scripts/seed-demo-data.js
   ```

5. Start the backend API:

   ```bash
   cd backend
   npm run dev
   ```

6. Start the frontend (Next.js) application:

   ```bash
   cd frontend
   npm run dev
   ```

The app will be available at `http://localhost:3000`. Log in with `aisling@example.com / password123` or `maya@example.com / password123` to explore the demo claims.

## Notes

- The AI assistant requires a valid OpenAI API key. Without an internet connection, `services/ai.js` will fall back to a generic reply.
- Push notifications and OCR/photo quality validation are stubbed and can be extended in future iterations.

Enjoy exploring the ClaimsCompanion MVP!
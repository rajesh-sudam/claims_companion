# ClaimsCompanion 🛡️

ClaimsCompanion is an **AI-powered insurance claims platform** designed to simplify and speed up the claims process for both customers and insurers.  
It integrates a **Next.js frontend** with a **Python backend**, enhanced with **AI assistants** for claim validation, guidance, chat support, and fraud detection.

---

## 🚀 Features

- **User Authentication** – Secure registration, login, and JWT-based sessions  
- **Claims Management** – Create, update, and track insurance claims in real time  
- **AI Assistant** – OpenAI-powered helper for validation, fraud detection & guidance  
- **Chat & Escalation** – Integrated chat with agents and AI suggestions  
- **Notifications** – Real-time claim updates via WebSockets  
- **PWA Support** – Installable progressive web app with offline-ready functionality  

---

## 🛠️ Tech Stack

- **Frontend:** Next.js (React, TypeScript, TailwindCSS, PWA-ready)  
- **Backend:** Pythoon  
- **Database:** PostgreSQL  
- **AI Integration:** OpenAI API  
- **Containerization:** Docker & Docker Compose  

---

## 📂 Project Structure
claimscompanion/
├── backend_py/              # Python backend (FastAPI + Alembic + PostgreSQL)
│   ├── alembic/             # Database migrations
│   │   ├── versions/        # Migration scripts
│   │   └── env.py           # Alembic environment config
│   ├── app/                 # Main FastAPI application
│   │ 
│   │   ├── rag.py           # Retrieval-Augmented Generation logic
│   │   ├── routes/          # API route definitions
│   │   │   ├── admin.py     # Admin endpoints
│   │   │   ├── chat.py      # Chat endpoints
│   │   │   ├── claims.py    # Claims CRUD & tracking
│   │   │  
│   │   ├── services/        # Business logic & AI integrations
│   │   │   ├── ai.py        # AI assistant integration (OpenAI, RAG)
│   │   │   ├── ai_validation.py # AI validation (OCR/photo quality)
│   │   │   
│   │   ├── models/          # (Optional) SQLAlchemy ORM models
│   │   ├── schemas/         # (Optional) Pydantic request/response schemas
│   │   └── main.py          # FastAPI entry point
│   ├── requirements.txt     # Python dependencies
│   └── .env.example         # Backend environment variables
│
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
│
└── README.md                # Project overview & setup instructions




## ⚡ Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/rajesh-sudam/claims_companion.git
cd claims_companion

-Copy the backend .env.example to .env:

cp backend/.env.example backend/.env

DATABASE_URL (PostgreSQL connection)

OPENAI_API_KEY (for AI features)

JWT_SECRET

⚡Run with Docker Compose
docker-compose up --build





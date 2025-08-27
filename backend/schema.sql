-- Users Table
CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  email VARCHAR(255) UNIQUE NOT NULL,
  password VARCHAR(255) NOT NULL,
  phone VARCHAR(20),
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Claims Table
CREATE TABLE IF NOT EXISTS claims (
  id SERIAL PRIMARY KEY,
  claim_number VARCHAR(20) UNIQUE NOT NULL,
  user_id INTEGER REFERENCES users(id),
  claim_type VARCHAR(50) NOT NULL,
  status VARCHAR(50) DEFAULT 'submitted',
  incident_date DATE,
  incident_description TEXT,
  estimated_completion DATE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Claim Progress Table
CREATE TABLE IF NOT EXISTS claim_progress (
  id SERIAL PRIMARY KEY,
  claim_id INTEGER REFERENCES claims(id),
  step_id VARCHAR(50),
  step_title VARCHAR(200),
  status VARCHAR(20),
  completed_at TIMESTAMP,
  description TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documents Table
CREATE TABLE IF NOT EXISTS claim_documents (
  id SERIAL PRIMARY KEY,
  claim_id INTEGER REFERENCES claims(id),
  file_name VARCHAR(255),
  file_url VARCHAR(500),
  document_type VARCHAR(100),
  status VARCHAR(50) DEFAULT 'pending_review',
  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chat Messages Table
CREATE TABLE IF NOT EXISTS chat_messages (
  id SERIAL PRIMARY KEY,
  claim_id INTEGER REFERENCES claims(id),
  message_type VARCHAR(20),
  message_text TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Notifications Table
CREATE TABLE IF NOT EXISTS notifications (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  claim_id INTEGER REFERENCES claims(id),
  type VARCHAR(50),
  title VARCHAR(200),
  message TEXT,
  sent_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
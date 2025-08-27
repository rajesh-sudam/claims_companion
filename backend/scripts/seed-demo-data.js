/*
 * Seed demo data for ClaimsCompanion.
 * This script inserts sample users, claims, progress, documents, chat messages and notifications
 * to help demonstrate the application during development and demo.
 *
 * Run with: node scripts/seed-demo-data.js
 */

const db = require('../src/db');
const bcrypt = require('bcrypt');

async function seed() {
  try {
    // Create users
    const passwordHash = await bcrypt.hash('password123', 10);
    const userRes = await db.query(
      `INSERT INTO users (email, password, first_name, last_name, phone)
       VALUES
         ('aisling@example.com', $1, 'Aisling', 'Murphy', '0831234567'),
         ('maya@example.com', $1, 'Maya', 'Patel', '0859876543')
       RETURNING id, email`,
      [passwordHash],
    );
    const user1 = userRes.rows[0];
    const user2 = userRes.rows[1];
    // Create claims
    const claim1Res = await db.query(
      `INSERT INTO claims (claim_number, user_id, claim_type, status, incident_date, incident_description, estimated_completion)
       VALUES
         ('CLM2025001', $1, 'motor', 'assessment_in_progress', '2025-01-15', 'Rear-end collision at traffic lights', '2025-03-15'),
         ('CLM2025002', $2, 'health', 'medical_review', '2025-01-10', 'Hospital visit for appendicitis', '2025-02-28')
       RETURNING id, claim_number`,
      [user1.id, user2.id],
    );
    const claim1 = claim1Res.rows[0];
    const claim2 = claim1Res.rows[1];
    // Claim progress
    await db.query(
      `INSERT INTO claim_progress (claim_id, step_id, step_title, status, completed_at, description)
       VALUES
         ($1, 'submitted', 'Claim Submitted', 'completed', NOW(), 'Your claim has been received and assigned number CLM2025001'),
         ($1, 'initial_review', 'Initial Review', 'completed', NOW(), 'Our team has reviewed your submission for completeness'),
         ($1, 'assessment', 'Assessment in Progress', 'active', NOW(), 'An assessor has been assigned and will contact you soon'),
         ($2, 'submitted', 'Claim Submitted', 'completed', NOW(), 'Your claim has been received and assigned number CLM2025002'),
         ($2, 'initial_review', 'Initial Review', 'completed', NOW(), 'Our team has reviewed your submission for completeness'),
         ($2, 'medical_review', 'Medical Review', 'active', NOW(), 'Your case is under medical review')
      `,
      [claim1.id, claim2.id],
    );
    console.log('Demo data seeded successfully.');
  } catch (err) {
    console.error('Error seeding demo data:', err);
  } finally {
    db.pool.end();
  }
}

seed();
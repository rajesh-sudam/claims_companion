const express = require('express');
const db = require('../db');
const { query } = require('../db');
const jwt = require('jsonwebtoken');

const router = express.Router();

// Middleware to authenticate token (duplicate of auth.js to avoid circular dependency)
const authenticate = (req, res, next) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) {
    return res.status(401).json({ error: 'Authorization header missing' });
  }
  const token = authHeader.split(' ')[1];
  if (!token) {
    return res.status(401).json({ error: 'Token missing' });
  }
  try {
    const payload = jwt.verify(token, process.env.JWT_SECRET);
    req.user = payload;
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Invalid token' });
  }
};

// Create new claim
router.post('/', authenticate, async (req, res) => {
  const {
    claim_type,
    incident_date,
    incident_description,
    estimated_completion,
  } = req.body;
  try {
    // Generate unique claim number (simple timestamp-based)
    const claimNumber = 'CLM' + Date.now().toString();
    const result = await db.query(
      `INSERT INTO claims (claim_number, user_id, claim_type, status, incident_date, incident_description, estimated_completion)
       VALUES ($1, $2, $3, $4, $5, $6, $7)
       RETURNING id, claim_number, claim_type, status, incident_date, incident_description, estimated_completion`,
      [
        claimNumber,
        req.user.id,
        claim_type,
        'submitted',
        incident_date,
        incident_description,
        estimated_completion || null,
      ],
    );
    const claim = result.rows[0];
    // Insert initial claim_progress step
    await db.query(
      `INSERT INTO claim_progress (claim_id, step_id, step_title, status, completed_at, description)
       VALUES ($1, $2, $3, $4, $5, $6)`,
      [
        claim.id,
        'submitted',
        'Claim Submitted',
        'completed',
        new Date(),
        `Your claim has been received and assigned number ${claim.claim_number}`,
      ],
    );
    return res.status(201).json({ claim });
  } catch (err) {
    console.error('Error creating claim:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// Get user's claims
router.get('/', authenticate, async (req, res) => {
  try {
    const result = await db.query(
      `SELECT id, claim_number, claim_type, status, incident_date, estimated_completion, created_at, updated_at
       FROM claims WHERE user_id = $1 ORDER BY created_at DESC`,
      [req.user.id],
    );
    return res.json({ claims: result.rows });
  } catch (err) {
    console.error('Error getting claims:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// Get specific claim by ID
router.get('/:id', authenticate, async (req, res) => {
  const { id } = req.params;
  try {
    const result = await db.query(
      `SELECT id, claim_number, claim_type, status, incident_date, incident_description, estimated_completion, created_at, updated_at
       FROM claims WHERE id = $1 AND user_id = $2`,
      [id, req.user.id],
    );
    const claim = result.rows[0];
    if (!claim) {
      return res.status(404).json({ error: 'Claim not found' });
    }
    return res.json({ claim });
  } catch (err) {
    console.error('Error getting claim:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// Update claim (allows updating status or description)
router.put('/:id', authenticate, async (req, res) => {
  const { id } = req.params;
  const { status, incident_description, estimated_completion } = req.body;
  try {
    // Only update if claim belongs to user
    const result = await db.query(
      `UPDATE claims SET status = COALESCE($1, status),
                          incident_description = COALESCE($2, incident_description),
                          estimated_completion = COALESCE($3, estimated_completion),
                          updated_at = CURRENT_TIMESTAMP
       WHERE id = $4 AND user_id = $5
       RETURNING id, claim_number, status, incident_description, estimated_completion`,
      [status || null, incident_description || null, estimated_completion || null, id, req.user.id],
    );
    const claim = result.rows[0];
    if (!claim) {
      return res.status(404).json({ error: 'Claim not found or unauthorized' });
    }
    // Emit update via socket
    const { getIO } = require('../socket');
    const io = getIO();
    if (io) {
      const room = `claim_${id}`;
      io.to(room).emit('claim_updated', {
        id: claim.id,
        status: claim.status,
        incident_description: claim.incident_description,
        estimated_completion: claim.estimated_completion,
      });
    }
    return res.json({ claim });
  } catch (err) {
    console.error('Error updating claim:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// Get claim progress
router.get('/:id/progress', authenticate, async (req, res) => {
  const { id } = req.params;
  try {
    // Ensure claim belongs to user
    const claimResult = await db.query('SELECT id FROM claims WHERE id = $1 AND user_id = $2', [id, req.user.id]);
    if (claimResult.rows.length === 0) {
      return res.status(404).json({ error: 'Claim not found' });
    }
    const progressResult = await db.query(
      `SELECT id, step_id, step_title, status, completed_at, description
       FROM claim_progress WHERE claim_id = $1 ORDER BY created_at ASC`,
      [id],
    );
    return res.json({ progress: progressResult.rows });
  } catch (err) {
    console.error('Error getting claim progress:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// Upload document (dummy implementation)
router.post('/:id/documents', authenticate, async (req, res) => {
  const { id } = req.params;
  // In a real implementation, we would handle file uploads via multipart/form-data
  // For this MVP skeleton we assume the client uploads via a third-party service and sends file details
  const { file_name, file_url, document_type } = req.body;
  if (!file_name || !file_url || !document_type) {
    return res.status(400).json({ error: 'file_name, file_url, and document_type are required' });
  }
  try {
    // Ensure claim belongs to user
    const claimResult = await db.query('SELECT id FROM claims WHERE id = $1 AND user_id = $2', [id, req.user.id]);
    if (claimResult.rows.length === 0) {
      return res.status(404).json({ error: 'Claim not found' });
    }
    const result = await db.query(
      `INSERT INTO claim_documents (claim_id, file_name, file_url, document_type, status)
       VALUES ($1, $2, $3, $4, $5)
       RETURNING id, file_name, file_url, document_type, status, uploaded_at`,
      [id, file_name, file_url, document_type, 'pending_review'],
    );
    return res.status(201).json({ document: result.rows[0] });
  } catch (err) {
    console.error('Error uploading document:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;
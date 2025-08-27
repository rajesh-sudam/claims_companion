const express = require('express');
const jwt = require('jsonwebtoken');
const db = require('../db');

const router = express.Router();

// Auth middleware
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

// Get notifications for current user
router.get('/', authenticate, async (req, res) => {
  try {
    const result = await db.query(
      `SELECT id, claim_id, type, title, message, sent_at, created_at
       FROM notifications
       WHERE user_id = $1
       ORDER BY created_at DESC`,
      [req.user.id],
    );
    return res.json({ notifications: result.rows });
  } catch (err) {
    console.error('Error getting notifications:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// Mark notifications as read (not tracked individually, simple stub)
router.post('/mark-read', authenticate, async (req, res) => {
  // For this MVP stub we won't update DB; just return success
  return res.json({ message: 'All notifications marked as read' });
});

module.exports = router;
const express = require('express');
const jwt = require('jsonwebtoken');
const db = require('../db');

const router = express.Router();

// Authentication middleware
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

// Send a new message for a claim
router.post('/:claimId/messages', authenticate, async (req, res) => {
  const { claimId } = req.params;
  const { message_text, message_type } = req.body;
  if (!message_text || !message_type) {
    return res.status(400).json({ error: 'message_text and message_type are required' });
  }
  try {
    // Ensure claim belongs to user
    const claimResult = await db.query('SELECT id FROM claims WHERE id = $1 AND user_id = $2', [claimId, req.user.id]);
    if (claimResult.rows.length === 0) {
      return res.status(404).json({ error: 'Claim not found' });
    }
    const result = await db.query(
      `INSERT INTO chat_messages (claim_id, message_type, message_text)
       VALUES ($1, $2, $3)
       RETURNING id, claim_id, message_type, message_text, created_at`,
      [claimId, message_type, message_text],
    );
    // TODO: emit via socket.io to other connected clients if needed
    const message = result.rows[0];
    // Emit user message to room
    const { getIO } = require('../socket');
    const io = getIO();
    if (io) {
      const room = `claim_${claimId}`;
      io.to(room).emit('chat_message', message);
    }
    // Trigger AI response asynchronously if message_type is 'user'
    if (message_type === 'user') {
      const AIClaimsAssistant = require('../services/ai');
      if (io) {
        // Emit typing indicator
        const room = `claim_${claimId}`;
        io.to(room).emit('typing', { from: 'ai' });
      }
      (async () => {
        try {
          const aiContent = await AIClaimsAssistant.generateResponse(claimId, message_text);
          // Insert AI message into DB
          const aiRes = await db.query(
            `INSERT INTO chat_messages (claim_id, message_type, message_text)
             VALUES ($1, $2, $3)
             RETURNING id, claim_id, message_type, message_text, created_at`,
            [claimId, 'ai', aiContent],
          );
          const aiMessage = aiRes.rows[0];
          // Emit AI message
          const { getIO } = require('../socket');
          const ioInstance = getIO();
          if (ioInstance) {
            const room = `claim_${claimId}`;
            ioInstance.to(room).emit('chat_message', aiMessage);
          }
        } catch (err) {
          console.error('Error generating AI response:', err);
        }
      })();
    }
    return res.status(201).json({ message });
  } catch (err) {
    console.error('Error sending message:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// Get chat history for a claim
router.get('/:claimId/history', authenticate, async (req, res) => {
  const { claimId } = req.params;
  try {
    // Ensure claim belongs to user
    const claimResult = await db.query('SELECT id FROM claims WHERE id = $1 AND user_id = $2', [claimId, req.user.id]);
    if (claimResult.rows.length === 0) {
      return res.status(404).json({ error: 'Claim not found' });
    }
    const result = await db.query(
      `SELECT id, message_type, message_text, created_at
       FROM chat_messages
       WHERE claim_id = $1
       ORDER BY created_at ASC`,
      [claimId],
    );
    return res.json({ history: result.rows });
  } catch (err) {
    console.error('Error getting chat history:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

// Escalate chat to human agent
router.post('/:claimId/escalate', authenticate, async (req, res) => {
  const { claimId } = req.params;
  try {
    // Ensure claim belongs to user
    const claimResult = await db.query('SELECT id FROM claims WHERE id = $1 AND user_id = $2', [claimId, req.user.id]);
    if (claimResult.rows.length === 0) {
      return res.status(404).json({ error: 'Claim not found' });
    }
    // Insert agent message into chat history
    const text = 'A human claims handler has been notified and will join this conversation shortly.';
    const result = await db.query(
      `INSERT INTO chat_messages (claim_id, message_type, message_text)
       VALUES ($1, $2, $3)
       RETURNING id, claim_id, message_type, message_text, created_at`,
      [claimId, 'ai', text],
    );
    const message = result.rows[0];
    // Emit message to room
    const { getIO } = require('../socket');
    const io = getIO();
    if (io) {
      const room = `claim_${claimId}`;
      io.to(room).emit('chat_message', message);
    }
    return res.json({ message });
  } catch (err) {
    console.error('Error escalating:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
});

module.exports = router;
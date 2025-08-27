const express = require('express');
const http = require('http');
const cors = require('cors');
const bodyParser = require('body-parser');
const { Server } = require('socket.io');
const dotenv = require('dotenv');

// Load environment variables
dotenv.config();

const authRoutes = require('./routes/auth');
const claimsRoutes = require('./routes/claims');
const chatRoutes = require('./routes/chat');
const notificationsRoutes = require('./routes/notifications');
const aiRoutes = require('./routes/ai');

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST'],
  },
});

// Set Socket.IO instance for other modules
const socketModule = require('./socket');
socketModule.setIO(io);

// Middleware
app.use(cors());
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/claims', claimsRoutes);
app.use('/api/chat', chatRoutes);
app.use('/api/notifications', notificationsRoutes);
app.use('/api/ai', aiRoutes);

// Socket.io connection
io.on('connection', (socket) => {
  console.log('Client connected:', socket.id);
  // Join a claim-specific room
  socket.on('join_claim', (claimId) => {
    const room = `claim_${claimId}`;
    socket.join(room);
    console.log(`Socket ${socket.id} joined room ${room}`);
  });
  // Leave a claim-specific room
  socket.on('leave_claim', (claimId) => {
    const room = `claim_${claimId}`;
    socket.leave(room);
    console.log(`Socket ${socket.id} left room ${room}`);
  });
  socket.on('disconnect', () => {
    console.log('Client disconnected:', socket.id);
  });
});

// Start the server
const PORT = process.env.PORT || 4000;
server.listen(PORT, () => {
  console.log(`API server listening on port ${PORT}`);
});
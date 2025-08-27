// socket.js
// This module stores a reference to the Socket.IO server instance.

let io;

module.exports = {
  setIO: (ioInstance) => {
    io = ioInstance;
  },
  getIO: () => io,
};
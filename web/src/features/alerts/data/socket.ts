import { io, type Socket } from 'socket.io-client';
import { config } from '../../../config';

// The only place that creates the Socket.IO connection (namespace /events, path /socket.io, same
// origin through the gateway or the dev proxy; integration-plan §6).
export function connectEvents(): Socket {
  return io(config.eventsUrl, { path: '/socket.io', transports: ['websocket', 'polling'] });
}

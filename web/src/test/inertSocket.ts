// Inert stand-in for socket.io-client in tests that render the whole App: no network, never connects.
export const inertSocketModule = {
  io: () => {
    const socket = { on: () => socket, disconnect: () => undefined };
    return socket;
  },
};

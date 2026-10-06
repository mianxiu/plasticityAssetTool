// Referrers describe navigation, not necessarily the containing CAD window.
// Start with a handshake; only the actual parent can establish its origin.
export function createParentChannel(parent) {
  let origin = '*';
  return {
    send(data) { parent.postMessage(data, origin); },
    receive(event) {
      if (event.source !== parent) return false;
      origin = event.origin === 'null' || !event.origin ? '*' : event.origin;
      return true;
    },
  };
}

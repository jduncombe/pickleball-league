// CloudFront Function (viewer request) for the /api/* behaviour.
// The API serves its routes at the root (/leagues, /health, ...), so strip the
// /api prefix: /api/leagues/1 -> /leagues/1. Query strings are untouched.
function handler(event) {
  var request = event.request;
  request.uri = request.uri.replace(/^\/api/, "") || "/";
  return request;
}

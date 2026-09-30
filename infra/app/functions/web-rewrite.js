// CloudFront Function (viewer request) for the static site.
// The Next.js export writes pages as <path>/index.html (trailingSlash: true);
// S3 has no directory indexes, so map /league/teams/ and /league/teams to
// /league/teams/index.html. Requests for files (with an extension) pass through.
function handler(event) {
  var request = event.request;
  var uri = request.uri;

  if (uri.endsWith("/")) {
    request.uri = uri + "index.html";
  } else if (uri.split("/").pop().indexOf(".") === -1) {
    request.uri = uri + "/index.html";
  }
  return request;
}

// Reassemble spam-obfuscated email links (see layouts/shortcodes/email.html).
// The address is stored split across data-user / data-domain so it never
// appears as a scrapable "user@domain" string in the page source. Loaded with
// `defer`, so the DOM is already parsed when this runs.
(function () {
  var links = document.querySelectorAll("a.email-link");
  for (var i = 0; i < links.length; i++) {
    var el = links[i];
    var user = el.getAttribute("data-user");
    var domain = el.getAttribute("data-domain");
    if (!user || !domain) continue;

    var addr = user + "@" + domain;
    var href = "mailto:" + addr;
    var subject = el.getAttribute("data-subject");
    if (subject) href += "?subject=" + encodeURIComponent(subject);
    el.setAttribute("href", href);

    // If no custom label was set, show the real address as the link text.
    if (!el.getAttribute("data-label")) el.textContent = addr;
  }
})();

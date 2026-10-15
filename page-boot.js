(function () {
  var script = document.currentScript;
  var src = script && script.getAttribute("data-src");
  if (!src) return;
  fetch(src).then(function (response) {
    if (!response.ok) throw new Error(String(response.status));
    return response.text();
  }).then(function (html) {
    document.open();
    document.write(html);
    document.close();
  }).catch(function () {
    document.body.textContent = "This page could not be loaded.";
  });
})();

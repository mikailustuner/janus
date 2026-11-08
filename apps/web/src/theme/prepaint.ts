/**
 * Pre-paint script (experience design §7, Req 6.7, 9.2, P17). Inlined in <head>; runs before the
 * first paint, reads the settings document in try/catch, validates each field and sets the
 * <html> attributes. Any failure leaves the defaults (Night Pharmacy, all off). It is plain ES5
 * source so the bundler never touches it, and the property test runs the same string. There is
 * no face attribute any more: one set of tokens per theme on every route (DP48).
 */

export const SETTINGS_KEY = "janus.v1.settings";

export const PREPAINT_SOURCE = `(function (d, getStorage) {
  var root = d.documentElement;
  var theme = "two-faces", large = "off", reduce = "off";
  try {
    var s = getStorage();
    var raw = s ? s.getItem(${JSON.stringify(SETTINGS_KEY)}) : null;
    var doc = raw ? JSON.parse(raw) : null;
    if (doc && typeof doc === "object" && doc.v === 1) {
      if (doc.theme === "glass" || doc.theme === "two-faces") theme = doc.theme;
      if (doc.largeText === true) large = "on";
      if (doc.reduceTransparency === true) reduce = "on";
    }
  } catch (e) {}
  root.setAttribute("data-theme-style", theme);
  root.setAttribute("data-large-text", large);
  root.setAttribute("data-reduce-transparency", reduce);
})(document, function () { try { return window.localStorage; } catch (e) { return null; } });`;

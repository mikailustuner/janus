/**
 * Pre-paint script (experience design §7, Req 6.7, 9.2, P17). Inlined in <head>; runs before the
 * first paint, reads the settings document in try/catch, validates each field and sets the
 * <html> attributes. Any failure leaves the defaults (Two Faces, shadow face, all off). It is
 * plain ES5 source so the bundler never touches it, and the property test runs the same string.
 */

/** Routes on the light face: the researcher area, the doctor page and the demo doctor page. */
export const LIGHT_ROUTE =
  /^\/(?:(?:en|tr|de|fr|es)\/)?(?:research|demo\/doctor)(?:\/|$)|^\/o(?:\/|$)/;

export const SETTINGS_KEY = "janus.v1.settings";

export const PREPAINT_SOURCE = `(function (d, getStorage, path) {
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
  var face = ${LIGHT_ROUTE.toString()}.test(String(path || "")) ? "light" : "shadow";
  root.setAttribute("data-theme-style", theme);
  root.setAttribute("data-face", face);
  root.setAttribute("data-large-text", large);
  root.setAttribute("data-reduce-transparency", reduce);
})(document, function () { try { return window.localStorage; } catch (e) { return null; } }, location.pathname);`;

export function faceFor(pathname: string): "light" | "shadow" {
  return LIGHT_ROUTE.test(pathname) ? "light" : "shadow";
}

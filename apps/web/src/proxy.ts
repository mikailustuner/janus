import createMiddleware from "next-intl/middleware";

import { routing } from "./i18n/routing";

export default createMiddleware(routing);

export const config = {
  // All pathnames except /api, /_next, /_vercel, the doctor page /o (no locale segment; the
  // token is in the fragment, experience DP19) and files with an extension.
  matcher: "/((?!api|_next|_vercel|o(?:$|/)|.*\\..*).*)",
};

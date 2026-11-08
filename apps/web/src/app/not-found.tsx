// Rendered when the [locale] segment is not a supported locale.
import messages from "../../messages/en.json";

export default function GlobalNotFound() {
  return (
    <html lang="en">
      <body>
        <main>
          <h1>404 — Page not found</h1>
        </main>
        {/* Rule 9 (safety audit A7): the disclaimer on every page, also this one. */}
        <footer>
          <p>{messages.Disclaimer.text}</p>
        </footer>
      </body>
    </html>
  );
}

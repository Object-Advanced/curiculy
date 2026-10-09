// Runs before first paint: pick the saved theme and, with no saved sign-in,
// show the sign-in page instead of an empty app shell. A same-origin file
// (not an inline script) so the Content-Security-Policy can be script-src 'self'.
(function () {
    try {
        if (localStorage.getItem("theme") === "dark") {
            document.documentElement.setAttribute("data-theme", "dark");
        }
        if (!localStorage.getItem("auth_token")) {
            document.documentElement.setAttribute("data-auth", "required");
        }
    } catch (error) {
        document.documentElement.setAttribute("data-auth", "required");
    }
})();

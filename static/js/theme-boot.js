// Runs before first paint: pick the saved theme and, with no saved sign-in,
// show the sign-in page instead of an empty app shell. A same-origin file
// (not an inline script) so the Content-Security-Policy can be script-src 'self'.
(function () {
    try {
        if (localStorage.getItem("theme") === "dark") {
            document.documentElement.setAttribute("data-theme", "dark");
        }
        var token = localStorage.getItem("auth_token");
        if (!token) {
            document.documentElement.setAttribute("data-auth", "required");
        } else {
            // A signed-in child gets the kid look from the first frame.
            try {
                var part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
                var claims = JSON.parse(atob(part + "===".slice((part.length + 3) % 4)));
                if (claims.role === "child") {
                    document.documentElement.setAttribute("data-persona", "kid");
                }
            } catch (error) {
                /* unreadable token: the app signs out and shows sign-in */
            }
        }
    } catch (error) {
        document.documentElement.setAttribute("data-auth", "required");
    }
})();

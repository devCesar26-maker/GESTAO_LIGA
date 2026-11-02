import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import { purgeLegacyAuthStorage } from "./lib/legacyTokenCleanup";
import "./styles.css";

// Older builds stored the JWT in web storage; drop those keys on boot.
purgeLegacyAuthStorage();

// Apply the saved theme before the first paint (login/register pages do not
// render the Layout that owns the toggle).
document.documentElement.dataset.theme = localStorage.getItem("liga.theme") || "dark";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  </React.StrictMode>,
);

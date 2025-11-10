Mock Model Registry Frontend

Files
- index.html — home / recent models
- upload.html — upload mock form
- model.html — view, rate, delete
- ingest.html — ingest URL, mock-evaluate and upload if above threshold
- license_check.html — simple license compatibility checker
- enumerate.html — regex-based search over uploaded models
- styles.css — shared styles
- app.js — simple client-side logic and mock data (uses localStorage)

How to run (Windows PowerShell)
1. Open terminal and change directory to where this project lives:


2. Start a simple HTTP server (Python 3 required):

   python -m http.server 8000

3. Open the frontend in your browser:

   http://localhost:8000/mock_registry_frontend/

Notes
- This is a mock UI. All operations are client-side and stored in localStorage.
- Reloading the page preserves models in localStorage. Clearing storage will reset to sample models.
- Use the "Enumerate / Search" page to run regular-expression searches across model name/desc/license/url.

Screenshots
- Open pages and take screenshots with your OS/browser tools.

If you want, I can add a small Node/Express mock API next to this static UI to simulate server behavior. 

# OYB chatbot — Phase 1 Vercel deployment

This package deploys only the customer-facing Flask chatbot. It does not include the admin dashboard or a database. Customer messages are not persisted in this phase.

## Included
- Flask app (`app.py`)
- Chat page (`templates/index.html`)
- CSS and supplied product images (`public/static/`)
- Gemini API integration through an environment variable

## Before deployment
1. Rotate/revoke the Gemini API key that was previously hard-coded in the original source file.
2. Create a new Gemini API key. Do not put it in source code or commit it to Git.
3. Add `GEMINI_API_KEY` in Vercel Project Settings → Environment Variables (Production and Preview as needed).
4. Add `FLASK_SECRET_KEY` with a long random value in Vercel Environment Variables.
5. Deploy this project folder to Vercel.

Vercel detects Flask from `app.py` and `requirements.txt`. Static files are in `public/` and the HTML template is in `templates/`.

## Deploy through GitHub
1. Create a new GitHub repository, e.g. `oyb-chatbot-vercel`.
2. Upload the *contents* of this folder to the repository root (not the outer folder itself).
3. In Vercel, choose Add New → Project and import this repository.
4. Keep the detected Python/Flask settings; no custom build command or output directory is required.
5. Add `GEMINI_API_KEY` and `FLASK_SECRET_KEY` before deploying, then deploy.
6. Test the homepage, `/health`, product buttons, follow-up questions, and a general Gemini question.

## Notes
- This deployment does not call the local dashboard at `127.0.0.1:5001`.
- This deployment does not save customer enquiries. Supabase can be added in Phase 2 if time permits.
- `sleep.png` was not included among the supplied assets; the sleep product card will still appear but its image will be hidden until that file is added to `public/static/`.
- No logo image was supplied in the current assets; the page displays the OYB text branding.

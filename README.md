# xyz
helo
\n\n## Email setup and fast notifications\n\nSee [NOTIFICATIONS_SETUP.md](NOTIFICATIONS_SETUP.md) for Resend/SMTP configuration, Render environment variables, and how background email delivery keeps booking buttons responsive.\n

## Important for mobile email buttons on Render

Set `BASE_URL` to the exact public `https://...onrender.com` URL for this service. Email action links are built from this URL; `localhost` links work only on the computer running the app and will fail from a phone. Teacher action links open a confirmation page first; tap the action button there to submit the change.

Cloud email uses the Resend HTTPS API when `RESEND_API_KEY` is configured. The shared `onboarding@resend.dev` sender is only for limited testing to the Resend account owner email. For student/teacher delivery, verify a domain in Resend and set `RESEND_FROM_EMAIL` to an address on that verified domain.


## Render email URL configuration
Set `BASE_URL` to the exact public HTTPS URL of the deployed CampusSlot service (for example, `https://your-service.onrender.com`). Do not use localhost. The app config derives `SERVER_NAME`, `PREFERRED_URL_SCHEME`, and `APPLICATION_ROOT` from this setting so background email notifications can build appointment and action URLs without an active Flask request.

Resend restriction: `onboarding@resend.dev` is a testing sender and Resend may restrict recipients to the account owner email. To send to students/teachers, verify a domain in Resend and set `RESEND_FROM_EMAIL` to a sender address on that verified domain. Never put API keys into the ZIP or source control.

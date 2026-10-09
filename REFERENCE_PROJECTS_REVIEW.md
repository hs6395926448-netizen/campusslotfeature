# Reference ZIP review

I reviewed the supplied ZIPs for email/notification patterns. I did not copy entire projects into CampusSlot because they solve different problems and would make the current Flask app heavier or incompatible.

- **`chatwoot-develop`**: a separate Ruby on Rails customer-support platform. Its email inbox, integrations, and frontend are not drop-in components for this Flask booking app.
- **`cloudflare-email`**: a Cloudflare Worker email API based on MailChannels. Its own README warns that MailChannels' free Cloudflare Workers sending service was sunset in 2024, so it is not a safe default for a new transactional email feature.
- **`cloudflare_temp_email`**: a disposable/inbound temporary-mail service built around Cloudflare Workers; it is not the transactional notification sender CampusSlot needs.
- **`cloud-mail`**: a standalone Cloudflare Workers mail platform with Resend support. It is a separate mail application, not a library to embed into CampusSlot.
- **`xyz-main-email-queue-fixed`**: this is the actual CampusSlot base. It already contains Resend and email templates/action links. The important speed issue was that notification calls could send synchronously when no Celery/Redis broker was configured.

## What changed in this package

- Normal booking, cancellation, and registration notifications now schedule in a small in-process background pool if Redis/Celery is not configured.
- If a broker is configured and healthy, the existing Celery queue is used.
- If the optional broker is down, the request path falls back to the background pool instead of waiting for SMTP/Resend.
- The admin's explicit test-email action remains synchronous so it can report actual delivery errors.
- Added email setup notes and simplified the Render Blueprint to web + database for a low-cost setup.

## Limitation to understand

An in-process background pool is best for a simple deployment and fast button responses, but it is not a durable queue: a process restart can interrupt unsent messages. For important/high-volume production mail, configure Redis plus a Celery worker. Real external email delivery also requires a valid Resend sender/domain or working SMTP credentials.

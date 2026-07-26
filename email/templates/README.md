# Transactional Email Templates

These Factorio-branded Markdown templates support borrower application reminders.
They are rendered by `utils.email_templates` and used by the Customer Service
agent. Available variables are `first_name`, `resume_url`, and `support_email`.

Templates are draft-only until Postmark is configured. A future sender must:

- require a named Admin approval or an approved lifecycle trigger;
- use a verified Factorio sender signature and HTTPS application link;
- record template, recipient, trigger, provider message ID, and delivery status;
- support suppression, unsubscribe rules where applicable, retries, and webhooks;
- never include bank credentials, API keys, or sensitive account data.

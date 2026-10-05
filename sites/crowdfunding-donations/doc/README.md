# FundSpark (`crowdfunding-donations`)

A Kickstarter/GoFundMe-style crowdfunding site. Users browse and search
campaigns, back a project through a reward-tier checkout, start their own
campaign, post updates, and save, follow, subscribe to or share campaigns.

- URL: `/sites/crowdfunding-donations/` (simulated domain `fundspark.com`)
- Data split: held-out (test) site

## Pages

| Route | Page |
|---|---|
| `/` | Campaign grid with search, status dropdown (Active, Funded, Expired, Cancelled) and sort dropdown |
| `/category/<name>` | Campaigns in one category |
| `/campaign/<id>` | Campaign detail: funding progress, reward tiers, updates, follow creator, save, subscribe, share menu |
| `/campaign/<id>/checkout` | Pledge checkout: backer info, shipping for physical rewards, payment method, consent |
| `/create` | "Start a Project" form (title, description, goal, category, dates) |
| `/dashboard` | The user's own campaigns and backed campaigns (login required) |
| `/login`, `/register` | Sign-in and registration |

JSON endpoints under `/api/` create campaigns, post updates and record pledges.

## Interactions and macros

- Search campaigns: `search`
- Filter by status: `filter_by_dropdown`
- Sort by Trending, Newest, Most Funded, Most Backed, Ending Soon: `sort_by_form`
- Start a campaign, post an update: `create_by_form`
- Back a project through checkout and the 2FA payment step: `checkout_by_form`, `pay_by_form`
- Save a campaign, subscribe to updates: `toggle_relationship`
- Share a campaign link: `share_by_form`
- Read funding progress, backers and updates: `report_information`

The per-macro UI locations are listed in `data/macro_locations.yaml` under `crowdfunding-donations`.

## Data

- Tables: `crowdfunding_donations_campaigns`, `crowdfunding_donations_pledges`,
  `crowdfunding_donations_users`.
- Login reads `session["user_id"]`, so the global auto-login signs in as user 1.
- A form pledge is recorded, a "Pledge confirmed" email goes to WebMail, and the
  payment then goes through the shared 2FA page (`/verify-payment`, code sent to
  WebMail). Verification posts a "Donations" debit to banking. JSON pledges
  skip 2FA and post the debit directly.
- Registering emits `signup` (password-vault entry and welcome email).

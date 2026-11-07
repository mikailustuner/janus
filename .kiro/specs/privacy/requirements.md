# Requirements: Privacy and Consent

> Draft seed. Refine with Kiro, then let Kiro generate `design.md` and `tasks.md`. See `.kiro/steering/privacy.md`.

## Introduction
Health data is the biggest risk in Janus. Privacy is a product feature: on-device processing, stateless APIs, explicit consent, k-anonymity and differential privacy — designed to GDPR (EU), KVKK (Türkiye) and US consumer-health-data expectations at the same time.

## Requirements

### Requirement 1: On-device processing
#### Acceptance criteria
1. THE client SHALL decode barcodes and run OCR in the browser and SHALL NOT upload images.
2. THE client SHALL keep the medication list in browser storage by default and SHALL work without an account.
3. THE client SHALL render the doctor note PDF in the browser.

### Requirement 2: Stateless medical endpoints and logging
#### Acceptance criteria
1. Medical API endpoints SHALL NOT persist request bodies.
2. Logs SHALL contain only request id, route, status and latency; THE system SHALL NOT log ingredients, product codes, events, dates or note content.

### Requirement 3: Consent and donation
**User story:** As a user, I want to choose exactly what I share and be able to take it back.

#### Acceptance criteria
1. WHEN a user chooses to donate THE client SHALL show a specific consent screen, in the user's language, listing every field to be shared and the legal basis (explicit consent).
2. THE system SHALL store only: 5-year age band, optional sex, region (TR / EU / US), ingredients, event term, direction (adverse/benefit), week.
3. THE system SHALL return a deletion token; WHEN it is presented THE system SHALL delete the donation completely and confirm.
4. THE system SHALL store donations in an EU hosting region and SHALL state the hosting region on the privacy page.

### Requirement 4: Aggregate protection
#### Acceptance criteria
1. THE system SHALL suppress any aggregate from user data representing fewer than k = 20 people.
2. THE system SHALL add Laplace noise with a configured ε to user-data counts.

### Requirement 5: Transparency
#### Acceptance criteria
1. THE privacy page SHALL explain, in all supported languages, what stays on the device, what is sent, what is stored, for how long, and how to delete it.
2. THE product SHALL NOT claim certifications or audits that have not been performed.

## Properties to test (PBT candidates)
- For any request to a medical endpoint, the captured log line contains none of the request's medical values.
- For any stored donation, the stored record contains only allowed fields.
- After deletion with a valid token, no query returns the donation.
- Suppression: for any dataset, no output cell is derived from fewer than 20 contributors.

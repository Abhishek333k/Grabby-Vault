# Lemon Squeezy verification / onboarding pack

**Product:** GrabbyVault Pro (Windows)  
**Publisher:** SilenVault  
**Store:** https://store.silenvault.com  
**Support:** silenvault@gmail.com (or your LS store email)

This folder is for **Lemon Squeezy onboarding / risk / product verification teams** and for your own QA before go-live.

---

## 1. What the product is

| Field | Value |
|--------|--------|
| Name | GrabbyVault Pro — Windows Video Downloader |
| Type | Desktop software (Windows 10/11) |
| Delivery | Digital download (zip/exe) + **license key** |
| Payments | Lemon Squeezy checkout |
| Ads | **None** |
| Free tier | Same app; limited quality (720p) & 1 concurrent job |
| Pro unlock | Lemon Squeezy license key activated **in the app** |

**Not sold:** unlimited multi-PC seats by default.  
**Recommended LS setting:** Generate license keys = ON · **Activation limit = 1** · Lifetime (or as you set).

---

## 2. How licensing works (technical)

We use the **public License API** (no merchant API key inside the client):

| Action | Endpoint | Body |
|--------|----------|------|
| Activate | `POST /v1/licenses/activate` | `license_key`, `instance_name` |
| Validate | `POST /v1/licenses/validate` | `license_key`, optional `instance_id` |
| Deactivate | `POST /v1/licenses/deactivate` | `license_key`, `instance_id` |

Headers (per [License API docs](https://docs.lemonsqueezy.com/api/license-api)):

- `Accept: application/json`
- `Content-Type: application/x-www-form-urlencoded`

**Customer flow**

1. Buy on Lemon Squeezy → key in email / receipt.  
2. Install GrabbyVault → **Pro** → paste key → **Activate**.  
3. App sends `instance_name` = machine label (`GrabbyVault-<pc>-<hash>`).  
4. App stores returned `instance.id` for later **validate** / **deactivate**.  
5. While open, app **validates** every ~3 minutes (single-seat).  
6. **Release seat** / **Take over this PC** uses **deactivate** then **activate**.

**Key status handling:** `inactive` / `active` accepted; `expired` / `disabled` demote Pro.

---

## 3. Verification checklist (for LS team)

Use a **test-mode** product or 100% discount coupon.

### A. Purchase

- [ ] Checkout completes  
- [ ] Receipt email includes **license key**  
- [ ] Order appears in LS dashboard  
- [ ] License key visible under order / licenses  

### B. Activate (happy path)

- [ ] Install Windows build from file attached to product  
- [ ] Open app → Pro → paste key → Activate  
- [ ] UI shows **PRO**  
- [ ] LS dashboard shows **1 activation** with instance name  

### C. Single seat / limit

- [ ] Product activation limit = **1**  
- [ ] Second machine Activate fails with limit message  
- [ ] **Take over this PC** on machine B succeeds  
- [ ] Machine A loses Pro within one heartbeat (~3 min) or on next open  

### D. Deactivate

- [ ] **Release seat** in app  
- [ ] LS shows usage decreased / inactive  
- [ ] Same key can Activate again  

### E. Validate offline / network

- [ ] After activate, disconnect network briefly — Pro may remain within grace  
- [ ] After long offline (beyond grace) + failed validate → Free until online validate  

### F. Negative cases

- [ ] Random garbage key → clear error  
- [ ] Disabled key in LS dashboard → demote / fail activate  
- [ ] Expired key (if you set length) → fail  

---

## 4. Suggested product listing (copy)

See `product-listing.md` in this folder.

---

## 5. Demo video script (optional, 60–90s)

See `demo-script.md`.

---

## 6. Screenshots to attach in LS product

| # | Capture |
|---|---------|
| 1 | Main window (dark UI, URL field, queue) |
| 2 | Quality picker (1080p / Pro) |
| 3 | License / Pro dialog (Activate + Take over) |
| 4 | Settings health (ffmpeg OK) |
| 5 | SilenVault store product card (optional) |

Place files in `ls-verification/screenshots/` when ready.

---

## 7. Build notes for reviewers

```text
Windows 10/11 64-bit
No admin required for typical zip run
ffmpeg.exe + ffprobe.exe must ship in bin\
Node.js optional (improves YouTube format list for yt-dlp)
```

**Privacy:** License API calls only go to `api.lemonsqueezy.com`.  
No ads, no third-party analytics required for licensing.

---

## 8. Contact

| Role | Contact |
|------|---------|
| Publisher | SilenVault |
| Support | silenvault@gmail.com |
| Site | https://store.silenvault.com |

---

*This pack is informational for verification. It does not replace Lemon Squeezy merchant policies.*

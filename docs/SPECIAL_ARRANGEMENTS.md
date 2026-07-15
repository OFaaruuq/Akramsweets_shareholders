# Special Arrangements

Special Arrangements are rules that **redirect a bonus percentage of some shareholders’ base shares to one recipient** when a monthly period is calculated.

They do **not** change ownership percentages. Ownership still decides the initial split. Arrangements only move money *after* that split.

---

## Purpose

Use Special Arrangements when the company has an agreed side rule, for example:

- The owner receives an extra **20% of every other shareholder’s** monthly share  
- A manager receives **10% of one named shareholder’s** base share  
- A bonus applies on **profit months only**, or also on **loss months**

Without an arrangement, each shareholder simply gets:

`Net Profit × ownership %`

With an arrangement, part of some shareholders’ base shares is transferred to the recipient before the final payout is locked.

---

## How calculation works

For each monthly period:

1. Enter the full P&L and save. **Net Profit** is what gets distributed.
2. System calculates each shareholder’s **base share** from ownership %.
3. Active Special Arrangements (matching date + profit/loss) are applied.
4. Optional manual adjustments are applied.
5. **Final amount** is stored on the period (and later on certificates / reports).

### Formula (one arrangement)

For each **source** shareholder:

```
deduction = source base share × (bonus % ÷ 100)
```

- Source final share goes **down** by that deduction (on a profit month)
- Recipient final share goes **up** by the total of those deductions

The company total still adds up: what sources lose, the recipient gains.

---

## Example

Company **Net Profit = 100,000**

| Shareholder | Ownership | Base share |
|-------------|-----------|------------|
| Owner       | 30%       | 30,000     |
| A           | 40%       | 40,000     |
| B           | 30%       | 30,000     |

**Arrangement:** “Owner bonus” — **20%** of **all other** shareholders → Owner (applies on profit)

| Shareholder | Base | Arrangement | Final |
|-------------|------|-------------|-------|
| Owner       | 30,000 | +8,000 from A + 6,000 from B = **+14,000** | **44,000** |
| A           | 40,000 | **−8,000** | **32,000** |
| B           | 30,000 | **−6,000** | **24,000** |
| **Total**   | 100,000 | 0 | **100,000** |

On a **loss** month (−100,000) with the same rule enabled for losses, the same percentages apply with opposite signs: the recipient bears more of the loss; sources bear less.

---

## Two modes

### 1. All other shareholders (default)

Every active shareholder **except the recipient** contributes.

- New shareholders are included automatically  
- Best for a standing “owner / partner bonus from everyone else”

### 2. Selective sources

Only the shareholders you tick contribute.

- Recipient cannot be a source  
- At least one source is required  
- Best for a deal that involves specific people only

---

## Fields (what to enter)

| Field | Meaning |
|-------|---------|
| **Name** | Clear label, e.g. “Owner 20% from others” |
| **Recipient** | Who receives the redirected amounts (must be an **active** shareholder) |
| **Bonus %** | Percent of each **source’s base share** (not percent of company Net Profit) |
| **Apply on profit** | Run when Net Profit ≥ 0 |
| **Apply on loss** | Run when Net Profit &lt; 0 |
| **All other shareholders** | On = mode 1; Off = choose selective sources |
| **Source shareholders** | Who pays the bonus (selective mode only) |
| **Effective from / to** | Date range vs period end date; leave “to” blank for open-ended |
| **Active** | Off = ignored on new calculations |
| **Notes** | Optional internal note |

You must enable **at least one** of Apply on profit / Apply on loss.

---

## How to use (Admin / Owner)

Only **Owner** and **System Administrator** can manage arrangements. Finance can see results on periods and reports, but not edit the rules.

### Create

1. Open **Special Arrangements** in the sidebar  
   (URL: `/settings/arrangements`)
2. Fill the form on the page (or use **Add** / create flow if shown)
3. Choose recipient, bonus %, profit/loss flags, and all-others **or** selective sources
4. Save

The rule applies on the **next** monthly period calculation (and on recalculate for draft/review periods).

### Edit

1. Open the arrangement → **Edit**
2. Change fields → Save  
3. Approved (locked) periods are **not** changed automatically — only new calculations use the updated rule

### Deactivate / Activate

- **Deactivate** — stop using the rule for future calculations (history stays as calculated)
- **Activate** — turn it back on (blocked if recipient is inactive, or selective mode has no sources)

### Check before calculating a month

On **Enter Monthly Result**, the sidebar shows **Active Arrangements** for that period and any warnings (e.g. recipient missing from the ownership pool). Fix those before saving & calculating.

---

## Reading a shareholder statement

On period detail and PDF reports you will typically see:

1. **Ownership %** and **Base share**
2. **Arrangement deduction** (amount taken from this person)
3. **Arrangement received** (amount paid to this person from others)
4. **Manual adjustment** (if any)
5. **Final amount**

---

## Important rules & tips

- Ownership for the period must total **100%** before calculation.
- Bonus % is of each source’s **base share**, not of company Net Profit.
- Several arrangements can run together; they **stack**.
- A sole shareholder cannot fund themselves via “all others” (no other sources → rule is skipped).
- Inactive recipient → arrangement is skipped on calculation.
- Changing or deactivating a rule does **not** rewrite already **approved** periods.

---

## Who does what

| Role | Arrangements |
|------|----------------|
| Owner / Admin | Create, edit, activate, deactivate |
| Finance | Enter P&L periods; review distribution results |
| Shareholder (portal) | See final amounts / reports only |

---

## Quick FAQ

**Does this change ownership?**  
No. Ownership records stay the same.

**When does a new rule take effect?**  
On the next period calculation (or recalculate while the period is still draft/review).

**A new shareholder joined — do they pay the “all others” bonus?**  
Yes, automatically, if the arrangement uses “all other shareholders”.

**Can I use arrangements only in profit months?**  
Yes — enable Apply on profit and disable Apply on loss.

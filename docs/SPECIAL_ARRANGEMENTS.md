# Special Arrangements

Special Arrangements redirect a **bonus percentage of some shareholders’ base shares** to one recipient when a monthly period is calculated.

They do **not** change ownership percentages. Ownership still decides the initial split of the **shareholders’ Mudarabah pool**. Arrangements only move money *after* that split.

---

## Mudarabah context (required)

Distribution is **not** `Net Profit × ownership %` on the full Net Profit.

1. Enter **Approved Monthly Net Profit** from Odoo  
2. **Mudarabah split** (from System Settings, e.g. 50/50):  
   - Shareholders’ pool = Net Profit × shareholder %  
   - Managing partner (company) share = remainder  
3. Each shareholder’s **base share** = pool × ownership %  
4. **Special Arrangements** move amounts between those base shares  
5. Optional **manual adjustments**  
6. **Final amount** is locked on approve

Only the **shareholders’ pool** is redistributed by arrangements. The managing partner share is untouched.

See also [MUDARABAH.md](MUDARABAH.md) and [NET_PROFIT_DISTRIBUTION.md](NET_PROFIT_DISTRIBUTION.md).

---

## Purpose

Use Special Arrangements when the company has an agreed side rule, for example:

- The owner receives an extra **20% of every other shareholder’s** monthly base share  
- A manager receives **10% of one named shareholder’s** base share  
- A bonus applies on **profit months only**, or also on **loss months**

Without an arrangement, each shareholder simply gets:

`Shareholders’ pool × ownership %`

With an arrangement, part of some shareholders’ base shares is transferred to the recipient before the final payout is locked.

---

## How calculation works

For each monthly period:

1. Enter Net Profit (and optional Odoo reference). Save & calculate.  
2. System splits Net Profit into pool + managing partner share.  
3. System calculates each shareholder’s **base share** from ownership % of the **pool**.  
4. Active Special Arrangements (matching date + profit/loss) are applied.  
5. Optional manual adjustments are applied.  
6. **Final amount** is stored (certificates / reports use this).

### Formula (one arrangement)

For each **source** shareholder:

```
deduction = source base share × (bonus % ÷ 100)
```

- Source final share goes **down** by that deduction (on a profit month)  
- Recipient final share goes **up** by the total of those deductions  

The **pool** still adds up: what sources lose, the recipient gains.

---

## Example (Mudarabah 50% pool)

Company **Net Profit = 100,000**  
Shareholders’ pool (50%) = **50,000** · Managing partner = **50,000**

| Shareholder | Ownership | Base share (of pool) |
|-------------|-----------|----------------------|
| Owner       | 30%       | 15,000               |
| A           | 40%       | 20,000               |
| B           | 30%       | 15,000               |

**Arrangement:** “Owner bonus” — **20%** of **all other** shareholders → Owner (applies on profit)

| Shareholder | Base | Arrangement | Final |
|-------------|------|-------------|-------|
| Owner       | 15,000 | +4,000 from A + 3,000 from B = **+7,000** | **22,000** |
| A           | 20,000 | **−4,000** | **16,000** |
| B           | 15,000 | **−3,000** | **12,000** |
| **Pool total** | 50,000 | 0 | **50,000** |

On a **loss** month (−100,000) with the same rule enabled for losses, the same percentages apply with opposite signs on the loss pool.

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
| **Bonus %** | Percent of each **source’s base share** (of the pool — not of company Net Profit) |
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

1. Open **Special Arrangements** in the sidebar (`/settings/arrangements`)  
2. Choose recipient, bonus %, profit/loss flags, and all-others **or** selective sources  
3. Save  

The rule applies on the **next** monthly period calculation (and on recalculate for draft periods).

### Edit / Deactivate

- Edit fields → Save (approved periods are **not** rewritten)  
- **Deactivate** stops the rule for future calculations  

### Check before calculating a month

On **Monthly Mudarabah Profit Distribution**, the sidebar shows **Special Arrangements** and any warnings. Fix those before saving & calculating. Ownership must total **100.0000%**.

---

## Reading a shareholder statement

On period detail and PDF reports you will typically see:

1. **Ownership %** and **Original / base profit** (from the pool)  
2. **Arrangement adjustment** (net of deduction + received)  
3. **Manual adjustment** (if any)  
4. **Final profit**

---

## Important rules & tips

- Ownership for the period must total **100%** before calculation.  
- Bonus % is of each source’s **base share of the pool**, not of company Net Profit.  
- Several arrangements can run together; they **stack**.  
- A sole shareholder cannot fund themselves via “all others” (no other sources → rule is skipped).  
- Inactive recipient → arrangement is skipped on calculation.  
- Changing or deactivating a rule does **not** rewrite already **approved** periods.

---

## Who does what

| Role | Arrangements |
|------|----------------|
| Owner / Admin | Create, edit, activate, deactivate |
| Finance | Enter Net Profit periods; review distribution results |
| Shareholder (portal) | See final amounts / reports only |

---

## Quick FAQ

**Does this change ownership?**  
No. Ownership records stay the same.

**Does the managing partner share get arrangements?**  
No. Arrangements only move money inside the shareholders’ pool.

**When does a new rule take effect?**  
On the next period calculation (or recalculate while the period is still draft).

**A new shareholder joined — do they pay the “all others” bonus?**  
Yes, automatically, if the arrangement uses “all other shareholders”.

**Can I use arrangements only in profit months?**  
Yes — enable Apply on profit and disable Apply on loss.

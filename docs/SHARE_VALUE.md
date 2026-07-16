# Share value & capital register

## Purpose

Configure the **shareholder capital register** (from the company Excel sheet) for display and reporting:

| Item | Example (current register) |
|------|----------------------------|
| Value of 1 share | **USD 1,000** |
| Total shares | **1,220** |
| Total shareholder capital | **USD 1,220,000.48** |
| Company-owned assets (Murabaha) | **USD 423,000.00** |
| **Total company assets** | **USD 1,643,000.48** |

```text
Total Company Assets = Shareholder Capital + Company-Owned Assets
```

---

## Critical rule (Mudarabah)

**Company assets and shareholder capital are not used to calculate monthly profit distribution.**

Monthly process:

1. Import **Monthly Net Profit** from Odoo into a period  
2. Split by Mudarabah (e.g. **50% shareholders’ pool / 50% Akram Sweets**)  
3. Distribute the pool by each shareholder’s **ownership %**  
4. Apply special arrangements / manual adjustments if configured  

Capital totals appear on the **dashboard capital summary** and shareholder statements for financial reporting only.

---

## How to set it

1. Sign in as **Owner** or **Admin**  
2. Open **System Settings** → **Shareholder capital register**  
3. Enter:
   - **Value of 1 share** — e.g. `1000`  
   - **Total company shares** — e.g. `1220`  
   - **Company-owned assets (Murabaha)** — e.g. `423000`  
4. Save  

Per-shareholder **shares**, **capital**, and **ownership %** are maintained under **Shareholders** (or imported from CSV).

### Import from Excel / CSV

```bash
# 1. Fill data/shareholder_capital.csv with all 20 shareholders from Excel
# 2. Dry-run, then import
python scripts/import_shareholder_capital.py data/shareholder_capital.csv --dry-run
python scripts/import_shareholder_capital.py data/shareholder_capital.csv
```

CSV columns: `name,email,shares,capital,ownership_percent,is_owner,phone,country,country_code`

Ownership % across active shareholders must total **100.0000%** before a period can be calculated.

---

## Dashboard KPIs

### Capital Summary

- Total Shareholders / Active Shareholders  
- Total Shares  
- Total Shareholder Capital (sum of active `investment_amount`)  
- Company-Owned Assets (setting)  
- Total Company Assets (capital + company-owned)  

### Monthly Profit Summary

- Net Profit (from latest period / Odoo)  
- Shareholders’ Profit Pool  
- Akram Sweets’ Profit Share  
- Total Distributed  
- Remaining Undistributed  

---

## Notes

- Changing share value or company-owned assets does **not** rewrite past period calculations.  
- Profit formula remains: `Shareholders' pool × ownership %` (after Mudarabah split of Net Profit).  
- Excel “20% from some people” style bonuses belong in **Special Arrangements**, not in the capital register.  

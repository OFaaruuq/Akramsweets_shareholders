# Monthly periods: Net Profit from Odoo → Mudarabah → ownership distribution

## Rule

For each accounting period (e.g. monthly):

1. **Only Net Profit** is taken from Odoo (entered into this system with an optional Odoo reference).
2. Under **Mudarabah**, Net Profit is split (default **50% / 50%**):
   - **Shareholders' profit pool** — distributed by ownership %
   - **Akram Sweets (managing partner)** — retained by the company
3. Each shareholder’s base share is calculated from the **pool**, not from full Net Profit.

```
Shareholders' pool = Net Profit × mudarabah_shareholder_percent / 100
base_share = Shareholders' pool × (ownership % ÷ 100)
```

Then, if configured:

- Special arrangements may redirect a bonus % between shareholders  
- Manual adjustments may apply  

Shareholder distribution reconciles to the **pool** (± $0.01).

Other P&L lines (Income, Gross Profit, Expenses, etc.) are **optional notes only** and are **not** used for distribution.

See [MUDARABAH.md](MUDARABAH.md) for the full agreement rules (withdrawal, audit, reporting).

---

## How to enter a period

1. Open **Monthly Periods → Enter Monthly Result**  
2. Choose year / month  
3. Paste optional Odoo journal / period reference  
4. Enter **Net Profit (from Odoo)** — required  
5. Preview Mudarabah pools + ownership distribution  
6. Save → draft calculated → submit → approve  

---

## Ownership requirements

- Active shareholders’ ownership must total **100%** as of the period end date  
- Ownership is managed under **Shareholders** (investment %)  
- Calculation uses the ownership record effective for that month  

---

## What is not automatic (today)

There is **no live Odoo API connector** in the app yet.  
Finance copies **Net Profit** from Odoo into the period form (and may store the Odoo reference).  
Dashboard “from Odoo” KPI widgets are separate admin display figures, not the period distribution engine.

---

## Formula summary

| Step | Formula |
|------|---------|
| Input | Net Profit (Odoo) |
| Shareholders' pool | Net Profit × 50% (configurable) |
| Akram Sweets share | Net Profit − pool |
| Base share | Pool × ownership % |
| After arrangements | base ± arrangement deduction/received |
| After adjustments | ± manual adjustment |
| Final | stored on the period for reports & certificates |

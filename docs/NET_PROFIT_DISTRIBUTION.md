# Monthly periods: Net Profit from Odoo → ownership distribution

## Rule

For each accounting period (e.g. monthly):

1. **Only Net Profit** is taken from Odoo (entered into this system with an optional Odoo reference).
2. The system calculates each shareholder’s share from **ownership / investment %**.

```
base_share = Net Profit × (ownership % ÷ 100)
```

Then, if configured:

- Special arrangements may redirect a bonus % between shareholders  
- Manual adjustments may apply  

Company total still reconciles to Net Profit (± $0.01).

Other P&L lines (Income, Gross Profit, Expenses, etc.) are **optional notes only** and are **not** used for distribution.

---

## How to enter a period

1. Open **Monthly Periods → Enter Monthly Result**  
2. Choose year / month  
3. Paste optional Odoo journal / period reference  
4. Enter **Net Profit (from Odoo)** — required  
5. Preview distribution (shows ownership % and base shares)  
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
| Base share | Net Profit × ownership % |
| After arrangements | base ± arrangement deduction/received |
| After adjustments | ± manual adjustment |
| Final | stored on the period for reports & certificates |

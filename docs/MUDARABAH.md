# Mudarabah Profit Distribution

The company operates under a **Mudarabah (profit-sharing)** agreement between shareholders and Akram Sweets (managing partner).

## Split rule

| Party | Share of Monthly Net Profit |
|-------|-----------------------------|
| Shareholders' profit pool | **50%** (configurable) |
| Akram Sweets (managing partner) | **50%** (remainder) |

Example:

- Company Net Profit: USD 30,000  
- Shareholders' Profit Pool (50%): USD 15,000  
- Akram Sweets' Share (50%): USD 15,000  

Configure the shareholder % under **System Settings → Mudarabah**.

## Shareholder distribution

Only the **shareholders' pool** is distributed by ownership:

```
Shareholder Profit = (Ownership % ÷ 100) × Shareholders' Profit Pool
```

Then, if configured:

- Special arrangements may redirect a bonus % between shareholders  
- Manual adjustments may apply  

Distributed shareholder totals reconcile to the **pool** (± $0.01), not to full Net Profit.

## Monthly processing

1. Enter **Net Profit** from Odoo (and optional Odoo reference) on the period form  
2. System calculates Mudarabah pools and per-shareholder amounts  
3. Submit for review → Owner/Admin **Approve, Certify & Email**  
4. Reports, certificates, and audit logs are retained  

## Capital withdrawal

Shareholders can request return of capital from the portal (**Capital Withdrawal**).

- Request is recorded and enters an approval workflow  
- After **approval**, the company has up to **six (6) months** to return capital  
- Staff manage requests under **Capital Withdrawals** and the unified **Approvals** inbox  

## Period approval

1. Finance enters Net Profit and calculates distribution (draft)  
2. **Submit for Review** — figures lock; management is notified  
3. Owner/Admin **Approve & Certify** or **Return to draft** with a reason  
4. Reopening an approved period returns it to **draft** (must re-submit before re-approval)  

## Reports

- **Mudarabah Summary** — Net Profit, pool, Akram Sweets share, distributed totals  
- Period detail, individual shareholder statements, certificates, audit trail  

## Odoo integration

There is **no live Odoo API connector** yet. Finance imports **Monthly Net Profit** (and optional accounting-period reference / approval note) into each period. No other Odoo financial lines are required for shareholder calculations.

## Related docs

- [NET_PROFIT_DISTRIBUTION.md](NET_PROFIT_DISTRIBUTION.md) — period entry details  
- [SPECIAL_ARRANGEMENTS.md](SPECIAL_ARRANGEMENTS.md) — inter-shareholder bonuses  
- [SHARE_VALUE.md](SHARE_VALUE.md) — share unit / capital display  

# Analytics module

Staff menu: **Analytics** (`/analytics`).  
Investor menu: **Charts & Trends** (same URL; a private view).

Analytics is a **read-only year dashboard**. It does not calculate Mudarabah profit. Monthly Periods does that. Analytics **charts and tables approved months** for a chosen year, and (for staff) shows optional Display KPI figures beside them.

---

## Who sees what

| Role | Menu label | What they see |
|------|------------|----------------|
| Super Admin / System Admin / Finance | Analytics | Company P/L, all shareholders’ payouts, workflow counts, Display KPIs |
| Shareholder | Charts & Trends | **Only their** approved payouts, ownership, YTD / lifetime |
| Not signed in | — | Redirect to login |

Owner/Admin also see **Update Dashboard Figures** (opens Display KPIs). Finance and investors do not.

---

## What the module is for

**Use case (management):** Review a calendar year’s certified results — profit vs loss months, how much went to investors, who received what — without opening each period.

**Use case (finance):** Check that approved months exist for the year and export a CSV for the board pack.

**Use case (investor):** See my payout history, best/worst month, and download a statement from the table.

---

## Features and functionality

### 1. Year selector

- Dropdown of years that have **any** monthly period in the database.
- Default: current calendar year if it has data; otherwise the latest year with data.
- Changing year reloads the page (`?year=2026`).
- Charts, summary tiles, history table, and CSV all follow this year.

**Requirement:** Trend charts and the history table use **approved** periods only. Draft and in-review months do not appear on the graphs.

### 2. Export CSV

Button: **Export CSV** → `/analytics/export?year=…`

Staff columns:

| Period | Company P/L | Distributed | Type | Reports Sent | Shareholder Breakdown |
|--------|-------------|-------------|------|--------------|------------------------|

Investor columns:

| Period | Ownership % | My Payout | Reports Sent |
|--------|-------------|-----------|--------------|

File name: `shareholder-analytics-{year}.csv`. Newest periods first.

**Use case:** Attach the year to an email or open in Excel. Investors never receive other people’s amounts.

### 3. Update Dashboard Figures (Owner / Admin)

Opens **Display KPIs** (`/settings/dashboard`). Typed revenues, expenses, COGS, other income, notes.

These figures appear on Analytics **tiles** and **Operating Summary**. They are **not** used to split monthly profit.

**Use case:** Show a board-style “from Odoo” snapshot next to certified Mudarabah numbers.

### 4. Hero and shortcut

- Staff: company name, short explanation, **Manage Periods**.
- Investor: welcome by name, **View My Reports**.

### 5. Top KPI tiles (four cards)

**Staff**

| Tile | Source | Notes |
|------|--------|--------|
| Total Revenues | Display KPIs | Labelled “From Odoo — admin editable”. Optional % change vs previous period’s **Net Profit** (not revenues). |
| Monthly Profit / Loss | Latest period’s Net Profit | Latest period in the system (any status). |
| Active Shareholders | Count of active register rows | Link to Shareholders. |
| YTD Company Profit | Sum of **approved** Net Profit in the selected year | Link to staff Dashboard. |

**Investor**

| Tile | Source |
|------|--------|
| Latest Payout | Their last **approved** final amount |
| Year-to-Date | Sum of their approved finals in the selected year |
| Ownership % | Current effective ownership |
| Lifetime Total | Sum of all their approved finals (all years); caption still mentions selected year approved periods |

### 6. Year summary strip

From **approved** periods in the selected year:

| Staff | Investor |
|-------|----------|
| Profit months (Net Profit ≥ 0) | Positive payout months |
| Loss months | Negative payout months |
| Average monthly P/L | Average payout |
| Total distributed (sum of all investors’ finals) | Best period label |

### 7. Charts

Rendered with ApexCharts; currency and brand colour from settings.

| Chart | Staff | Investor |
|-------|--------|----------|
| **Profit & Distribution Reports** (combo) | Lines: Company P/L, Distributed. Bars: period revenues & expenses fields. Toolbar: download, zoom, reset. | Lines: My Payout, Cumulative view. No revenue/expense bars. |
| **Shareholder Payout Breakdown by Period** | Stacked bar, one series per investor, approved months | Hidden |
| **Profit Growth Rate** | Area: Company P/L vs Distributed | Area: My Payout vs Trend |
| **Shareholder Distribution** (donut) | Latest **approved** period: each investor’s final amount and ownership % | That investor only |

Empty data shows a placeholder (“N/A” / “No data”) rather than a broken chart.

### 8. Side lists

- **Shareholder Payouts:** up to six names from the donut period, amount and %.
- **Period Workflow Status (staff):** counts of Draft / In Review / Approved (**all years**), plus active arrangements. Not filtered by the year dropdown.
- **My Summary (investor):** approved report count, ownership %, YTD vs lifetime bar.

### 9. Operating Summary

**Staff:** Display KPI revenues, expenses, COGS, other income, net operating profit (revenues − expenses − COGS + other income), latest distributed, operating margin if revenues > 0, best and worst **approved** period by company Net Profit, optional notes.

**Investor:** Latest payout, YTD, lifetime, lowest payout period.

### 10. History table (up to 8 rows)

Newest first. Empty state if no approved months that year.

**Staff columns:** Period (link to period), Company P/L, Distributed, Profit/Loss badge, Reports Sent badge, per-person breakdown, open-period action.

**Investor columns:** Period (link to portal report), Ownership %, My Payout, Approved + Sent badges, view report + download PDF.

---

## Data rules (important)

1. **Charts and the year table = approved periods only** for the selected year.
2. **Workflow counts** (draft / review / approved) are **system-wide**, not year-scoped.
3. **Display KPIs** are typed; they never drive Mudarabah calculation.
4. Period **revenue/expense columns** on the combo chart come from the period record (often unused / zero). Do not treat those bars as the official Odoo P&L unless Finance filled them.
5. **YTD Company Profit** on Analytics is the sum of approved **Net Profit** for the year — the full company number, not the shareholders’ pool.
6. **Total Distributed** is the sum of investors’ **final amounts** (after arrangements and adjustments).
7. Investors **cannot** see other shareholders’ series, the stacked breakdown, Display KPIs, or period workflow.

---

## Use-case catalogue

| ID | Actor | Use case | How |
|----|--------|----------|-----|
| AN-01 | Management | Review the year’s certified profit vs what was paid to investors | Analytics → pick year → combo chart + Total Distributed |
| AN-02 | Management | See who earned what each month | Stacked breakdown + history table |
| AN-03 | Management | Count profit vs loss months | Year summary strip |
| AN-04 | Management | Spot the best and worst month | Operating Summary |
| AN-05 | Finance | Export the year for Excel / board pack | Export CSV |
| AN-06 | Finance | Jump from a row into the period to fix or inspect | Table → open period |
| AN-07 | Owner/Admin | Put Odoo display revenues on the same screen | Update Dashboard Figures |
| AN-08 | Owner/Admin | See how many months are still draft or in review | Period Workflow Status |
| AN-09 | Investor | See my payout trend for the year | Charts & Trends → year + combo/growth charts |
| AN-10 | Investor | Download my statement from analytics | Table → PDF |
| AN-11 | Investor | Confirm current ownership while looking at history | Ownership % tile → My Ownership |
| AN-12 | Anyone | Switch year without leaving analytics | Year dropdown |

---

## Related screens (not this module)

| Screen | Difference |
|--------|------------|
| **Dashboard** | Capital register + latest month pools. Home, not the year charts. |
| **Monthly Periods** | Where profit is **entered and calculated**. |
| **Mudarabah Summary** | Pool vs company share table (no charts). |
| **Display KPIs** | Where staff type the Analytics operating figures. |
| **Portal Dashboard** | Investor home; Charts & Trends is the analytics page. |

---

## Empty and edge cases

- No periods at all: year defaults to the current calendar year; charts show N/A; table says enter a monthly result.
- Year with only drafts: charts/table empty for that year; workflow still shows drafts.
- Investor with no approved months: tiles at zero; table empty; donut placeholder.
- CSV still downloads headers with no data rows if the year has no approved periods.

# Roles & Super Admin (Owner)

## Role hierarchy

| Role | Label in UI | Scope |
|------|-------------|--------|
| `owner` | **Super Admin (Owner)** | Full system control (highest) |
| `admin` | System Administrator | Day-to-day management (cannot manage Super Admins) |
| `finance` | Finance / Accounts | Enter periods, submit for review, view reports |
| `shareholder` | Shareholder | Portal only (own reports, ownership, withdrawals) |

## Super Admin privileges

The **Owner** is the system Super Admin and can:

- Approve / reject periods and capital withdrawals  
- Manage shareholders, arrangements, certificates  
- Open **System Settings**, images, dashboard KPIs, audit trail  
- Create and edit **all** staff users, including other Super Admins  
- See Super Admin shortcuts on the dashboard and in the profile menu  

## Protections

- System Admins **cannot** edit or demote Super Admin accounts  
- Only a Super Admin can assign the Super Admin (Owner) role  
- The **last active Super Admin** cannot be demoted or deactivated  

## Create a Super Admin

```bash
./venv/bin/python scripts/create_super_admin.py \
  --email you@example.com \
  --name "System Owner" \
  --force
```

Default role is `owner` (Super Admin). Use `--role admin` only for a System Administrator.

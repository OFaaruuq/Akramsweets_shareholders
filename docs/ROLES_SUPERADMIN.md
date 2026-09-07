# Roles & Super Admin (Owner)

## Role hierarchy

| Role | Label in UI | Scope |
|------|-------------|--------|
| `owner` | **Super Admin (Owner)** | Full system control (highest) |
| `admin` | System Administrator | Day-to-day management (cannot manage Super Admins) |
| `finance` | Finance / Accounts | Enter periods, submit for review, view reports |
| `shareholder` | Shareholder | Portal only (own reports, ownership, withdrawals) |

**Company Owner shareholders** (`Shareholder.is_owner`) with a login are also Super Admins. They keep their shareholder link so they can open **My Portal** (own statements) **and** every staff screen.

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
- Unchecking **Company owner** on the last Super Admin login is blocked until another Super Admin exists  

## Company Owner = Super Admin

When you mark a shareholder as **Company owner** and create (or already have) a portal login:

1. That login is promoted to Super Admin (`owner` role).
2. They land on the staff Dashboard after sign-in, with the full menu (periods, approvals, all shareholders, staff users, settings, analytics for the whole company).
3. **My Portal** stays available for their own reports, ownership, and capital withdrawal.
4. Creating another staff Super Admin is still allowed. The last Super Admin cannot lose that access by unchecking Company owner.

Existing Company Owner logins are promoted automatically on app start and at sign-in.

## Create a Super Admin

```bash
./venv/bin/python scripts/create_super_admin.py \
  --email you@example.com \
  --name "System Owner" \
  --force
```

Default role is `owner` (Super Admin). Use `--role admin` only for a System Administrator.

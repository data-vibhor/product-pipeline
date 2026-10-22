"""Seeded bugs for the sample invoice app. A good test suite fails on every one.

Each entry: (name, file, old text, new text). The old text must occur exactly once.
M01-M18 are business logic. M19-M24 are UI and security.
"""

MUTATIONS = [
    ("M01 yellow threshold off by one", "app/services.py", "if delta > 7:", "if delta > 8:"),
    ("M02 overdue days off by one", "app/services.py", "days_overdue = abs(delta)", "days_overdue = abs(delta) + 1"),
    ("M03 due-today test wrong", "app/services.py", "elif delta == 0:", "elif delta == 1:"),
    ("M04 no link for overdue", "app/services.py", 'if status.status not in ("due_today", "overdue"):', 'if status.status not in ("due_today",):'),
    ("M05 invoice lookup ignores owner (IDOR)", "app/services.py", "and_(Invoice.id == invoice_id, Invoice.user_id == user_id)", "(Invoice.id == invoice_id)"),
    ("M06 mark paid does nothing", "app/services.py", "invoice.paid_flag = True", "invoice.paid_flag = False"),
    ("M07 dashboard order reversed", "app/services.py", "Invoice.due_date.asc(), Invoice.created_at.asc()", "Invoice.due_date.desc(), Invoice.created_at.asc()"),
    ("M08 phone length schema", "app/schemas.py", "if len(v) < 10:", "if len(v) < 5:"),
    ("M09 phone length route", "app/main.py", "elif len(customer_phone) < 10:", "elif len(customer_phone) < 5:"),
    ("M10 password length", "app/schemas.py", "if len(v) < 8:", "if len(v) < 3:"),
    ("M11 login ignores password", "app/main.py", "if not user or not verify_password(login_data.password, user.password_hash):", "if not user:"),
    ("M12 zero amount allowed", "app/main.py", "if amount_decimal <= 0:", "if amount_decimal < 0:"),
    ("M13 logout keeps cookie", "app/main.py", '    rotate_csrf_token(request)\n    response = RedirectResponse(url="/login", status_code=303)\n    clear_session_cookie(response)', '    rotate_csrf_token(request)\n    response = RedirectResponse(url="/login", status_code=303)'),
    ("M14 delete keeps invoices", "app/services.py", "await session.execute(delete(Invoice).where(Invoice.user_id == user_id))", "pass"),
    ("M15 paid invoices vanish from dashboard", "app/main.py", "paid.append(resp)", "pass"),
    ("M16 new invoice starts paid", "app/services.py", "paid_flag=False,\n    )\n    session.add(invoice)", "paid_flag=True,\n    )\n    session.add(invoice)"),
    ("M17 wrong wa.me phone format", "app/services.py", 'return f"https://wa.me/{phone}?text={encoded_text}"', 'return f"https://wa.me/+{phone}?text={encoded_text}"'),
    ("M18 due-today message text", "app/services.py", 'WHATSAPP_DUE_TODAY_TEMPLATE = "Your payment of ₹{amount} is due today."', 'WHATSAPP_DUE_TODAY_TEMPLATE = "Your payment of ₹{amount} is due now."'),
    ("M19 Mark Paid button never shown", "app/templates/invoice_row.html", '{% if not inv.paid_flag and inv.status != "paid" %}', "{% if false %}"),
    ("M20 session cookie readable by scripts", "app/main.py", "max_age=settings.session_max_age,\n        httponly=True,", "max_age=settings.session_max_age,\n        httponly=False,"),
    ("M21 registration page without privacy gate", "app/main.py", 'if not request.cookies.get("privacy_accepted"):', "if False:"),
    ("M22 pay route skips the CSRF check", "app/main.py", '"""Mark invoice as paid."""\n    if not csrf_token or not validate_csrf_token(csrf_token, request):', '"""Mark invoice as paid."""\n    if False:'),
    ("M23 CSRF session comparison inverted", "app/csrf.py", "if secrets.compare_digest(token, session_token):\n                return True", "if not secrets.compare_digest(token, session_token):\n                return True"),
    ("M24 CSRF crypto check accepts anything", "app/csrf.py", "_csrf_signer.unsign(signed, max_age=max_age)\n        return True", "return True"),
]
